from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

from song_agent.release_operations import ReleaseOperationsStore
from song_agent.release_operations_audit import ReleaseOperationsAuditStore
from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
from song_agent.releases import ReleaseStore


def test_verify_release_operations_package_cli_json_report_out_and_tamper(tmp_path: Path) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops CLI", "release_type": "single_pack", "primary_artist": "MusicForge"})
    store = ReleaseOperationsStore(release_store=release_store)
    store.refresh(release.release_id)
    store.export_operations(release.release_id)
    store.build_zip(release.release_id)
    report_out = tmp_path / "verify-report.json"

    ok = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-release-operations-package", str(store.zip_path(release.release_id)), "--json", "--report-out", str(report_out)],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["status"] == "passed"

    tampered_zip = tmp_path / "tampered-cli.zip"
    with zipfile.ZipFile(store.zip_path(release.release_id), "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "operations-report.json":
                doc = json.loads(data.decode("utf-8"))
                doc["current_stage"] = "accepted"
                data = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    failed = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-release-operations-package", str(tampered_zip), "--json"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert failed.returncode == 1
    failed_payload = json.loads(failed.stdout)
    assert failed_payload["status"] == "failed"
    assert any(item["check_id"] == "operations_report_integrity" for item in failed_payload["blockers"])


def test_release_operations_runbook_cli_create_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    release_store = ReleaseStore()
    release = release_store.create_release({"name": "Runbook CLI", "release_type": "single_pack", "primary_artist": "MusicForge"})
    report_out = tmp_path / "runbook-result.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    created = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "release-operations-runbook", release.release_id, "--create", "--json", "--report-out", str(report_out)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert created.returncode == 0, created.stderr
    payload = json.loads(created.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    runbook_id = payload["runbook"]["runbook_id"]
    assert saved["runbook"]["runbook_id"] == runbook_id
    assert payload["summary"]["manual_required_count"] >= 1

    exported = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "release-operations-runbook", release.release_id, "--runbook-id", runbook_id, "--run-safe", "--export", "--zip", "--verify", "--require-current", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert exported.returncode == 0, exported.stderr
    exported_payload = json.loads(exported.stdout)
    assert exported_payload["zip"]["sha256"]
    assert exported_payload["verification_summary"]["status"] == "passed"

    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    verified = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-release-operations-runbook-package", str(runbook_store.zip_path(release.release_id, runbook_id)), "--json", "--require-current"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert verified.returncode == 0, verified.stderr
    verified_payload = json.loads(verified.stdout)
    assert verified_payload["status"] == "passed"


def test_verify_release_operations_archive_cli_json_report_out_and_tamper(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    release_store = ReleaseStore()
    release = release_store.create_release({"name": "Ops Archive CLI", "release_type": "single_pack", "primary_artist": "MusicForge"})
    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    report = operations_store.refresh(release.release_id)
    report["current_stage"] = "accepted"
    report["next_stage"] = "archived"
    report["summary"]["blocker_count"] = 0
    report["summary"]["warning_count"] = 0
    report["blockers"] = []
    report["warnings"] = []
    report["domains"] = {"submission_evidence": {"required": False, "status": "not_required", "summary": {}}}
    report["verifier_summaries"] = {"release": {"status": "passed"}}
    report["package_summaries"] = {"release_zip": {"exists": True, "status": "exists", "sha256": "0" * 64}, "distribution_packages": [], "submission_packages": [], "submission_evidence_packages": []}
    report["source_hash"] = "accepted-source-cli"
    report["source"] = {"fixture": "accepted"}
    from song_agent.release_operations import operations_report_integrity_hash

    report["integrity_hash"] = operations_report_integrity_hash(report)
    from song_agent.projectio import write_json

    write_json(operations_store.report_path(release.release_id), report)
    monkeypatch.setattr(operations_store, "build_report", lambda release_id, persist=False, now=None: report)
    monkeypatch.setattr(operations_store, "refresh", lambda release_id, now=None: report)
    runbook = runbook_store.create_from_operations_report(release.release_id)
    runbook["status"] = "completed"
    runbook["items"] = []
    from song_agent.release_operations_runbook import runbook_integrity_hash

    runbook["summary"] = {"total_count": 0, "safe_count": 0, "manual_count": 0, "completed_count": 0, "failed_count": 0, "blocked_count": 0, "manual_required_count": 0, "waived_count": 0, "pending_count": 0}
    runbook["integrity_hash"] = runbook_integrity_hash(runbook)
    write_json(runbook_store.runbook_path(release.release_id, runbook["runbook_id"]), runbook)
    signoff_store.signoff(release.release_id, {"signed_by": "cli-test"})
    signoff_store.export_archive(release.release_id)
    signoff_store.build_archive_zip(release.release_id)
    report_out = tmp_path / "archive-report.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    ok = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-release-operations-archive-package", str(signoff_store.archive_zip_path(release.release_id)), "--json", "--require-signed", "--report-out", str(report_out)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["status"] == "passed"
    assert json.loads(report_out.read_text(encoding="utf-8"))["status"] == "passed"

    tampered_zip = tmp_path / "tampered-archive-cli.zip"
    with zipfile.ZipFile(signoff_store.archive_zip_path(release.release_id), "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "operations-signoff.json":
                doc = json.loads(data.decode("utf-8"))
                doc["signed_by"] = "tampered"
                data = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    failed = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-release-operations-archive-package", str(tampered_zip), "--json", "--require-signed"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert failed.returncode == 1
    assert any(item["check_id"] == "operations_archive_signoff_payload_hash" for item in json.loads(failed.stdout)["blockers"])

    no_cr_reset = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "release-operations-signoff", release.release_id, "--reset", "--reason", "Reset without approved change request", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert no_cr_reset.returncode != 0
    assert "Change Request" in (no_cr_reset.stderr + no_cr_reset.stdout)

    change = signoff_store.create_change_request(release.release_id, {"reason": "Approved reset via CLI", "scope": ["operations"], "created_by": "cli-test"})
    change = signoff_store.update_change_request_status(release.release_id, change["change_request_id"], "approve", {"approved_by": "reviewer"})
    reset = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "release-operations-signoff", release.release_id, "--reset", "--reason", "Reset with approved change request", "--change-request-id", change["change_request_id"], "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert reset.returncode == 0, reset.stderr
    assert json.loads(reset.stdout)["summary"]["status"] == "reset"
    assert signoff_store.get_change_request(release.release_id, change["change_request_id"])["status"] == "applied"

    reuse = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "release-operations-signoff", release.release_id, "--reset", "--reason", "Reuse approved change request", "--change-request-id", change["change_request_id"], "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert reuse.returncode != 0
    assert "approved" in (reuse.stderr + reuse.stdout).lower()


def test_verify_release_portfolio_governance_audit_cli_json_report_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_audit import _accepted_governance_fixture

    portfolio_id, _queue_id, _governance_store, _signoff_store, audit_store = _accepted_governance_fixture(Path(".musicforge"), monkeypatch)
    audit_store.refresh(portfolio_id)
    audit_store.export_audit(portfolio_id)
    audit_store.build_zip(portfolio_id)
    report_out = tmp_path / "portfolio-governance-audit-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-audit-package",
            str(audit_store.zip_path(portfolio_id)),
            "--json",
            "--require-signed",
            "--require-archives",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["portfolio_id"] == portfolio_id
    assert saved["summary"]["ledger_hash"]


def test_release_portfolio_governance_audit_cli_refresh_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_audit import _accepted_governance_fixture

    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store = _accepted_governance_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-audit",
            "--portfolio-id",
            portfolio_id,
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--require-signed",
            "--require-archives",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["status"] == "passed"
    assert payload["zip"]["sha256"]
    assert payload["verification_summary"]["status"] == "passed"


def test_release_portfolio_governance_reviewer_pack_cli_refresh_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_reviewer_pack import _accepted_reviewer_fixture

    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, reviewer_store = _accepted_reviewer_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-reviewer-pack",
            "--portfolio-id",
            portfolio_id,
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--require-audit",
            "--require-signed",
            "--require-archives",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["status"] == "passed"
    assert payload["zip"]["sha256"]
    assert payload["verification_summary"]["status"] == "passed"
    assert reviewer_store.zip_path(portfolio_id).exists()


def test_verify_release_portfolio_governance_reviewer_pack_cli_json_report_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_reviewer_pack import _accepted_reviewer_fixture

    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, reviewer_store = _accepted_reviewer_fixture(Path(".musicforge"), monkeypatch)
    reviewer_store.refresh(portfolio_id)
    reviewer_store.export_pack(portfolio_id)
    reviewer_store.build_zip(portfolio_id)
    report_out = tmp_path / "portfolio-governance-reviewer-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-reviewer-pack",
            str(reviewer_store.zip_path(portfolio_id)),
            "--json",
            "--require-audit",
            "--require-signed",
            "--require-archives",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["portfolio_id"] == portfolio_id


def test_release_portfolio_governance_final_board_cli_refresh_import_sign_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_final_board import _accepted_final_board_fixture, _accepted_response

    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, store = _accepted_final_board_fixture(Path(".musicforge"), monkeypatch)
    response_path = tmp_path / "final-board-response.json"
    response_path.write_text(json.dumps(_accepted_response()), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-final-board",
            "--portfolio-id",
            portfolio_id,
            "--refresh",
            "--import-reviewer-response",
            str(response_path),
            "--require-reviewer-response",
            "--sign",
            "--signed-by",
            "cli-test",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-signed",
            "--require-reviewer-pack",
            "--require-audit",
            "--require-archives",
            "--require-reviewer-response",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["status"] == "passed"
    assert payload["signoff_summary"]["status"] == "signed"
    assert payload["zip"]["sha256"]
    assert payload["verification_summary"]["status"] == "passed"
    assert store.archive_zip_path(portfolio_id).exists()


def test_verify_release_portfolio_governance_final_board_cli_json_report_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_final_board import _accepted_final_board_fixture, _accepted_response

    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, store = _accepted_final_board_fixture(Path(".musicforge"), monkeypatch)
    store.import_reviewer_response(portfolio_id, _accepted_response())
    store.refresh_report(portfolio_id, {"require_reviewer_response": True})
    store.signoff(portfolio_id, {"signed_by": "cli-test"})
    store.export_archive(portfolio_id)
    store.build_archive_zip(portfolio_id)
    report_out = tmp_path / "portfolio-governance-final-board-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-final-board",
            str(store.archive_zip_path(portfolio_id)),
            "--json",
            "--require-signed",
            "--require-reviewer-pack",
            "--require-audit",
            "--require-archives",
            "--require-reviewer-response",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["portfolio_id"] == portfolio_id


def test_release_portfolio_governance_evidence_vault_cli_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_evidence_vault import _signed_final_board_vault_fixture

    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, _final_board_store, store = _signed_final_board_vault_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-evidence-vault",
            "--portfolio-id",
            portfolio_id,
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--deep",
            "--require-final-board",
            "--require-reviewer-pack",
            "--require-audit",
            "--require-archives",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["status"] == "passed"
    assert payload["zip"]["sha256"]
    assert payload["verification_summary"]["status"] == "passed"
    assert store.zip_path(portfolio_id).exists()


def test_verify_release_portfolio_governance_evidence_vault_cli_json_report_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_evidence_vault import _signed_final_board_vault_fixture

    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, _final_board_store, store = _signed_final_board_vault_fixture(Path(".musicforge"), monkeypatch)
    store.refresh_report(portfolio_id)
    store.export_vault(portfolio_id)
    store.build_zip(portfolio_id)
    report_out = tmp_path / "portfolio-governance-evidence-vault-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-evidence-vault",
            str(store.zip_path(portfolio_id)),
            "--json",
            "--strict",
            "--deep",
            "--require-final-board",
            "--require-reviewer-pack",
            "--require-audit",
            "--require-archives",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["portfolio_id"] == portfolio_id


def test_release_portfolio_governance_attestation_cli_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation import _attestation_fixture

    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, _final_board_store, _vault_store, store = _attestation_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-attestation",
            "--portfolio-id",
            portfolio_id,
            "--profile",
            "public_summary",
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-vault",
            "--require-final-board",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["status"] == "passed"
    assert payload["certificate"]["certificate_id"] == "pgc-000001"
    assert payload["zip"]["sha256"]
    assert payload["verification_summary"]["status"] == "passed"
    assert store.zip_path(portfolio_id).exists()


def test_verify_release_portfolio_governance_attestation_cli_json_report_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation import _attestation_fixture

    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, _final_board_store, _vault_store, store = _attestation_fixture(Path(".musicforge"), monkeypatch)
    store.refresh_report(portfolio_id)
    store.export_attestation(portfolio_id)
    store.build_zip(portfolio_id)
    report_out = tmp_path / "portfolio-governance-attestation-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-attestation",
            str(store.zip_path(portfolio_id)),
            "--json",
            "--strict",
            "--require-vault",
            "--require-final-board",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["portfolio_id"] == portfolio_id


def test_release_portfolio_governance_attestation_registry_cli_lifecycle_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation_registry import _registry_fixture

    portfolio_id, *_rest, store = _registry_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    registered = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-attestation-registry",
            "--portfolio-id",
            portfolio_id,
            "--register-current",
            "--refresh",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert registered.returncode == 0, registered.stderr
    registered_payload = json.loads(registered.stdout)
    entry_id = registered_payload["entry"]["entry_id"]

    managed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-attestation-registry",
            "--portfolio-id",
            portfolio_id,
            "--publish",
            entry_id,
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-current",
            "--require-published",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert managed.returncode == 0, managed.stderr
    payload = json.loads(managed.stdout)
    assert payload["summary"]["current_entry_id"] == entry_id
    assert payload["zip"]["sha256"]
    assert payload["verification_summary"]["status"] == "passed"
    assert store.zip_path(portfolio_id).exists()


def test_verify_release_portfolio_governance_attestation_registry_cli_json_report_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation_registry import _registry_fixture

    portfolio_id, *_rest, store = _registry_fixture(Path(".musicforge"), monkeypatch)
    entry = store.register_current_attestation(portfolio_id)["entry"]
    store.publish_entry(portfolio_id, entry["entry_id"], {"published_by": "test"})
    store.refresh_report(portfolio_id)
    store.export_registry(portfolio_id)
    store.build_zip(portfolio_id)
    report_out = tmp_path / "portfolio-governance-attestation-registry-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-attestation-registry",
            str(store.zip_path(portfolio_id)),
            "--json",
            "--strict",
            "--require-current",
            "--require-published",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["portfolio_id"] == portfolio_id


def test_release_portfolio_governance_attestation_portal_cli_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation_portal import _portal_fixture

    portfolio_id, *_rest, store = _portal_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    managed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-attestation-portal",
            "--portfolio-id",
            portfolio_id,
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-current",
            "--require-registry",
            "--require-attestation",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert managed.returncode == 0, managed.stderr
    payload = json.loads(managed.stdout)
    assert payload["summary"]["status"] == "passed"
    assert payload["zip"]["sha256"]
    assert payload["verification_summary"]["status"] == "passed"
    assert store.zip_path(portfolio_id).exists()


def test_verify_release_portfolio_governance_attestation_portal_cli_json_report_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation_portal import _portal_fixture

    portfolio_id, *_rest, store = _portal_fixture(Path(".musicforge"), monkeypatch)
    store.refresh_report(portfolio_id)
    store.export_portal(portfolio_id)
    store.build_zip(portfolio_id)
    report_out = tmp_path / "portfolio-governance-attestation-portal-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-attestation-portal",
            str(store.zip_path(portfolio_id)),
            "--json",
            "--strict",
            "--require-current",
            "--require-registry",
            "--require-attestation",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["portfolio_id"] == portfolio_id


def test_release_portfolio_governance_attestation_portal_review_cli_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation_portal import _portal_fixture

    portfolio_id, *_rest, store = _portal_fixture(Path(".musicforge"), monkeypatch)
    store.refresh_report(portfolio_id)
    store.export_portal(portfolio_id)
    store.build_zip(portfolio_id)
    report_out = tmp_path / "portal-review-pack-command.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    managed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-attestation-portal-review",
            "--portfolio-id",
            portfolio_id,
            "--refresh-pack",
            "--export-pack",
            "--zip-pack",
            "--verify-pack",
            "--strict",
            "--require-current",
            "--json",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = json.loads(managed.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))

    assert managed.returncode == 0, managed.stderr
    assert payload["summary"]["status"] == "ready"
    assert payload["zip"]["sha256"]
    assert payload["verification"]["status"] == "passed"
    assert saved["verification"]["status"] == "passed"


def test_release_portfolio_governance_attestation_accepted_evidence_cli_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation_portal import _portal_fixture
    from tests.test_release_portfolio_governance_attestation_portal_review import _response_payload
    from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
    from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore

    portfolio_id, *_rest, portal_store = _portal_fixture(Path(".musicforge"), monkeypatch)
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    review_store.refresh_pack(portfolio_id)
    response_zip = review_store.build_response_zip(portfolio_id, _response_payload())
    review_store.import_response(portfolio_id, {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")})
    accepted_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    report_out = tmp_path / "accepted-evidence-command.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    managed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-attestation-accepted-evidence",
            "--portfolio-id",
            portfolio_id,
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-current",
            "--json",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = json.loads(managed.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))

    assert managed.returncode == 0, managed.stderr
    assert payload["summary"]["external_review_status"] == "accepted"
    assert payload["zip"]["sha256"]
    assert payload["verification"]["status"] == "passed"
    assert saved["verification"]["status"] == "passed"

    offline_report = tmp_path / "accepted-evidence-offline.json"
    offline = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-attestation-accepted-evidence",
            str(accepted_store.zip_path(portfolio_id)),
            "--json",
            "--strict",
            "--require-current",
            "--report-out",
            str(offline_report),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    offline_payload = json.loads(offline.stdout)
    offline_saved = json.loads(offline_report.read_text(encoding="utf-8"))

    assert offline.returncode == 0, offline.stderr
    assert offline_payload["status"] == "passed"
    assert offline_saved["summary"]["accepted_evidence_id"]


def test_release_portfolio_governance_attestation_transparency_cli_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation_portal import _portal_fixture
    from tests.test_release_portfolio_governance_attestation_portal_review import _response_payload
    from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
    from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore
    from song_agent.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore

    portfolio_id, *_rest, portal_store = _portal_fixture(Path(".musicforge"), monkeypatch)
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    review_store.refresh_pack(portfolio_id)
    response_zip = review_store.build_response_zip(portfolio_id, _response_payload())
    imported = review_store.import_response(portfolio_id, {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")})
    accepted_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    accepted_store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})
    accepted_store.export_evidence(portfolio_id)
    accepted_store.build_zip(portfolio_id)
    accepted_store.verify_evidence(portfolio_id, {"strict": True, "require_current": True})
    portal_store.registry_store.export_registry(portfolio_id)
    portal_store.registry_store.build_zip(portfolio_id)
    portal_store.refresh_report(portfolio_id)
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)
    transparency_store = ReleasePortfolioGovernanceAttestationTransparencyStore(
        attestation_store=portal_store.attestation_store,
        registry_store=portal_store.registry_store,
        portal_store=portal_store,
        accepted_evidence_store=accepted_store,
    )
    report_out = tmp_path / "transparency-command.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    managed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-attestation-transparency",
            "--portfolio-id",
            portfolio_id,
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-current",
            "--require-accepted-evidence",
            "--require-contiguous-chain",
            "--notices",
            "--json",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = json.loads(managed.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))

    assert managed.returncode == 0, managed.stderr
    assert payload["summary"]["external_review_status"] == "accepted"
    assert payload["zip"]["sha256"]
    assert payload["verification"]["status"] == "passed"
    assert payload["notices"]
    assert saved["verification"]["status"] == "passed"

    offline_report = tmp_path / "transparency-offline.json"
    offline = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-attestation-transparency",
            str(transparency_store.zip_path(portfolio_id)),
            "--json",
            "--strict",
            "--require-current",
            "--require-accepted-evidence",
            "--require-contiguous-chain",
            "--report-out",
            str(offline_report),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    offline_payload = json.loads(offline.stdout)
    offline_saved = json.loads(offline_report.read_text(encoding="utf-8"))

    assert offline.returncode == 0, offline.stderr
    assert offline_payload["status"] == "passed"
    assert offline_saved["summary"]["event_count"] >= 4


def test_release_portfolio_governance_attestation_transparency_acknowledgement_cli_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation_transparency_acknowledgement import _accepted_response
    from tests.test_release_portfolio_governance_attestation_transparency_acknowledgement import _ack_fixture

    portfolio_id, _transparency_store, store = _ack_fixture(Path(".musicforge"), monkeypatch)
    pack = store.refresh_pack(portfolio_id)
    store.export_pack(portfolio_id)
    store.build_pack_zip(portfolio_id)
    imported = store.import_response(portfolio_id, {"content": _accepted_response(pack)})
    store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})
    store.export_evidence(portfolio_id)
    store.build_evidence_zip(portfolio_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    pack_report = tmp_path / "ack-pack-verify.json"
    pack_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-attestation-transparency-acknowledgement",
            str(store.pack_zip_path(portfolio_id)),
            "--json",
            "--strict",
            "--require-pack",
            "--require-transparency",
            "--report-out",
            str(pack_report),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    evidence_report = tmp_path / "ack-evidence-verify.json"
    evidence_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-attestation-transparency-acknowledgement",
            str(store.evidence_zip_path(portfolio_id)),
            "--json",
            "--strict",
            "--require-response",
            "--require-accepted",
            "--report-out",
            str(evidence_report),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    managed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-attestation-transparency-acknowledgement",
            "--portfolio-id",
            portfolio_id,
            "--verify-pack",
            "--verify-evidence",
            "--strict",
            "--require-transparency",
            "--require-accepted",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert pack_result.returncode == 0, pack_result.stderr
    assert evidence_result.returncode == 0, evidence_result.stderr
    assert json.loads(pack_result.stdout)["status"] == "passed"
    assert json.loads(evidence_result.stdout)["status"] == "passed"
    assert json.loads(pack_report.read_text(encoding="utf-8"))["status"] == "passed"
    assert json.loads(evidence_report.read_text(encoding="utf-8"))["status"] == "passed"
    assert managed.returncode == 0, managed.stderr
    managed_payload = json.loads(managed.stdout)
    assert managed_payload["pack_verification"]["status"] == "passed"
    assert managed_payload["evidence_verification"]["status"] == "passed"


def test_verify_release_portfolio_governance_attestation_portal_response_cli_json_report_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance_attestation_portal import _portal_fixture
    from tests.test_release_portfolio_governance_attestation_portal_review import _response_payload
    from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore

    portfolio_id, *_rest, portal_store = _portal_fixture(Path(".musicforge"), monkeypatch)
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    review_store.refresh_pack(portfolio_id)
    response_zip = review_store.build_response_zip(portfolio_id, _response_payload())
    report_out = tmp_path / "portal-response-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-attestation-portal-response",
            str(response_zip),
            "--json",
            "--strict",
            "--require-current",
            "--require-pack",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = json.loads(ok.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))

    assert ok.returncode == 0, ok.stderr
    assert payload["status"] == "passed"
    assert saved["summary"]["response_id"]


def test_verify_release_operations_audit_cli_json_report_out_and_tamper(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    release_store = ReleaseStore()
    release = release_store.create_release({"name": "Ops Audit CLI", "release_type": "single_pack", "primary_artist": "MusicForge"})
    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    report = operations_store.refresh(release.release_id)
    report["current_stage"] = "accepted"
    report["next_stage"] = "archived"
    report["summary"]["blocker_count"] = 0
    report["summary"]["warning_count"] = 0
    report["blockers"] = []
    report["warnings"] = []
    report["domains"] = {"submission_evidence": {"required": False, "status": "not_required", "summary": {}}}
    report["verifier_summaries"] = {"release": {"status": "passed"}}
    report["package_summaries"] = {"release_zip": {"exists": True, "status": "exists", "sha256": "0" * 64}, "distribution_packages": [], "submission_packages": [], "submission_evidence_packages": []}
    report["source_hash"] = "accepted-audit-cli"
    report["source"] = {"fixture": "accepted"}
    from song_agent.release_operations import operations_report_integrity_hash
    from song_agent.projectio import write_json

    report["integrity_hash"] = operations_report_integrity_hash(report)
    write_json(operations_store.report_path(release.release_id), report)
    monkeypatch.setattr(operations_store, "build_report", lambda release_id, persist=False, now=None: report)
    monkeypatch.setattr(operations_store, "refresh", lambda release_id, now=None: report)
    runbook = runbook_store.create_from_operations_report(release.release_id)
    runbook["status"] = "completed"
    runbook["items"] = []
    from song_agent.release_operations_runbook import runbook_integrity_hash

    runbook["summary"] = {"total_count": 0, "safe_count": 0, "manual_count": 0, "completed_count": 0, "failed_count": 0, "blocked_count": 0, "manual_required_count": 0, "waived_count": 0, "pending_count": 0}
    runbook["integrity_hash"] = runbook_integrity_hash(runbook)
    write_json(runbook_store.runbook_path(release.release_id, runbook["runbook_id"]), runbook)
    signoff_store.signoff(release.release_id, {"signed_by": "cli-test"})
    signoff_store.export_archive(release.release_id)
    signoff_store.build_archive_zip(release.release_id)
    from song_agent.release_operations_archive_verifier import verify_release_operations_archive_package, write_release_operations_archive_verification_report

    archive_report = verify_release_operations_archive_package(signoff_store.archive_zip_path(release.release_id), require_signed=True)
    write_release_operations_archive_verification_report(archive_report, signoff_store.operations_dir(release.release_id) / "operations-archive-verification-report.json")
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    audit_store.refresh(release.release_id)
    audit_store.export_audit(release.release_id)
    audit_store.build_zip(release.release_id)
    report_out = tmp_path / "audit-report.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    ok = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-release-operations-audit-package", str(audit_store.zip_path(release.release_id)), "--json", "--require-current", "--require-signed", "--require-archive", "--report-out", str(report_out)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["status"] == "passed"
    assert json.loads(report_out.read_text(encoding="utf-8"))["status"] == "passed"

    tampered_zip = tmp_path / "tampered-audit-cli.zip"
    with zipfile.ZipFile(audit_store.zip_path(release.release_id), "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "operations-audit-report.json":
                doc = json.loads(data.decode("utf-8"))
                doc["summary"]["entry_count"] = 1
                data = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    failed = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-release-operations-audit-package", str(tampered_zip), "--json", "--require-current", "--require-signed", "--require-archive"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert failed.returncode == 1
    assert any(item["check_id"] == "operations_audit_report_integrity" for item in json.loads(failed.stdout)["blockers"])

    command = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "release-operations-audit", release.release_id, "--refresh", "--export", "--zip", "--verify", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert command.returncode == 0, command.stderr
    payload = json.loads(command.stdout)
    assert payload["summary"]["entry_count"] >= 1
    assert payload["verification_summary"]["status"] in {"passed", "warning"}


def test_release_operations_reviewer_pack_cli_create_export_verify(tmp_path: Path, monkeypatch) -> None:
    from tests.test_release_operations_reviewer_pack import accepted_reviewer_fixture

    monkeypatch.chdir(tmp_path)
    release, _operations_store, _runbook_store, _signoff_store, _audit_store, reviewer_store = accepted_reviewer_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    created = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "release-operations-reviewer-pack", release.release_id, "--refresh", "--export", "--zip", "--verify", "--strict", "--require-audit", "--require-signed", "--require-archive", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert created.returncode == 0, created.stderr
    payload = json.loads(created.stdout)
    assert payload["summary"]["status"] == "passed"
    assert payload["verification_summary"]["status"] == "passed"

    report_out = tmp_path / "reviewer-verification.json"
    verified = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-release-operations-reviewer-pack", str(reviewer_store.zip_path(release.release_id)), "--json", "--strict", "--require-audit", "--require-signed", "--require-archive", "--report-out", str(report_out)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["status"] == "passed"


def test_release_portfolio_audit_cli_create_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_audit import portfolio_fixture

    release, second, _store = portfolio_fixture(Path(".musicforge"), monkeypatch, second_verified=True)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-audit",
            "--create",
            "--name",
            "CLI Portfolio",
            "--release-ids",
            f"{release.release_id},{second.release_id}",
            "--require-reviewer-packs",
            "--require-audit",
            "--require-archive",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert created.returncode == 0, created.stderr
    portfolio_id = json.loads(created.stdout)["portfolio"]["portfolio_id"]

    exported = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-audit",
            "--portfolio-id",
            portfolio_id,
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-reviewer-packs",
            "--require-audit",
            "--require-archive",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert exported.returncode == 0, exported.stderr
    exported_payload = json.loads(exported.stdout)
    assert exported_payload["summary"]["status"] == "passed"
    assert exported_payload["verification_summary"]["status"] == "passed"

    verified = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-audit-package",
            str(Path(".musicforge") / "portfolio-audits" / portfolio_id / "portfolio-audit.zip"),
            "--strict",
            "--require-reviewer-packs",
            "--require-audit",
            "--require-archive",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["status"] == "passed"


def test_release_portfolio_governance_queue_cli_create_run_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance import governance_fixture

    _release, _second, portfolio, _store = governance_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    portfolio_id = portfolio["portfolio_id"]

    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-queue",
            "--portfolio-id",
            portfolio_id,
            "--create",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert created.returncode == 0, created.stderr
    queue_id = json.loads(created.stdout)["queue"]["queue_id"]

    ran = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-queue",
            "--queue-id",
            queue_id,
            "--run-safe",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-manual-actions",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ran.returncode == 0, ran.stderr
    payload = json.loads(ran.stdout)
    assert payload["summary"]["status"] == "manual_required"
    assert payload["verification_summary"]["status"] == "passed"

    verified = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-package",
            str(Path(".musicforge") / "portfolio-governance-queues" / queue_id / "governance-queue.zip"),
            "--strict",
            "--require-manual-actions",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["status"] == "passed"


def test_release_portfolio_governance_signoff_cli_sign_archive_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from tests.test_release_portfolio_governance import governance_fixture

    _release, _second, portfolio, _store = governance_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    portfolio_id = portfolio["portfolio_id"]

    created = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "release-portfolio-governance-queue", "--portfolio-id", portfolio_id, "--create", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert created.returncode == 0, created.stderr
    queue_id = json.loads(created.stdout)["queue"]["queue_id"]

    prepared = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-queue",
            "--queue-id",
            queue_id,
            "--run-safe",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-manual-actions",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert prepared.returncode == 0, prepared.stderr

    signed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "release-portfolio-governance-signoff",
            "--queue-id",
            queue_id,
            "--sign",
            "--signed-by",
            "cli-test",
            "--export-archive",
            "--zip",
            "--verify",
            "--strict",
            "--require-signed",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert signed.returncode == 0, signed.stderr
    payload = json.loads(signed.stdout)
    assert payload["summary"]["status"] == "signed"
    assert payload["verification_summary"]["status"] == "passed"

    verified = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-release-portfolio-governance-archive-package",
            str(Path(".musicforge") / "portfolio-governance-queues" / queue_id / "governance-archive.zip"),
            "--strict",
            "--require-signed",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["status"] == "passed"
