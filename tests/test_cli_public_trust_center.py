from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_public_trust_center import _trust_center_fixture
from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore
from song_agent.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore
from song_agent.public_trust_center_distribution_kit_acceptance import response_payload_hash as kit_acceptance_response_payload_hash


def test_public_trust_center_cli_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, store = _trust_center_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "public-trust-center",
            "--center-id",
            "ptc-default",
            "--portfolio-id",
            portfolio_id,
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-registry-current",
            "--require-portal-current",
            "--require-transparency-current",
            "--require-acknowledgement-current",
            "--no-require-release-signoff",
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
    assert payload["verification"]["status"] == "passed"
    assert store.zip_path("ptc-default").exists()


def test_verify_public_trust_center_cli_json_report_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, store = _trust_center_fixture(Path(".musicforge"), monkeypatch)
    store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    store.export_center("ptc-default")
    store.build_zip("ptc-default")
    report_out = tmp_path / "public-trust-center-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-public-trust-center-package",
            str(store.zip_path("ptc-default")),
            "--json",
            "--strict",
            "--require-registry-current",
            "--require-portal-current",
            "--require-transparency-current",
            "--require-acknowledgement-current",
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

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["center_id"] == "ptc-default"


def test_public_trust_center_anchor_registry_cli(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, store = _trust_center_fixture(Path(".musicforge"), monkeypatch)
    store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    store.export_center("ptc-default")
    store.build_zip("ptc-default")
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=store)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "public-trust-center",
            "--center-id",
            "ptc-default",
            "--anchor-register",
            "--anchor-publish",
            "--anchor-export",
            "--anchor-zip",
            "--anchor-verify",
            "--require-anchor-registry-current",
            "--require-anchor-published",
            "--require-anchor-not-revoked",
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
    assert payload["anchor_verification"]["status"] == "passed"
    assert payload["anchor_summary"]["current_entry_status"] == "published"
    assert anchor_store.zip_path("ptc-default").exists()

    report_out = tmp_path / "anchor-registry-verification.json"
    verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-public-trust-center-anchor-registry-package",
            str(anchor_store.zip_path("ptc-default")),
            "--json",
            "--strict",
            "--require-current",
            "--require-anchor-published",
            "--require-anchor-not-revoked",
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

    assert verify.returncode == 0, verify.stderr
    verified = json.loads(verify.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert verified["status"] == "passed"
    assert saved["summary"]["current_entry_status"] == "published"

    ptc_verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-public-trust-center-package",
            str(store.zip_path("ptc-default")),
            "--json",
            "--strict",
            "--require-delivery-readiness",
            "--delivery-anchor",
            str(store.delivery_anchor_path("ptc-default")),
            "--anchor-registry",
            str(anchor_store.zip_path("ptc-default")),
            "--require-anchor-registry-current",
            "--require-anchor-published",
            "--require-anchor-not-revoked",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ptc_verify.returncode == 1
    ptc_payload = json.loads(ptc_verify.stdout)
    assert any(item["check_id"] == "ptc_anchor_registry_current_anchor" for item in ptc_payload["checks"])
    assert all(not item["check_id"].startswith("ptc_anchor_registry") for item in ptc_payload["blockers"])


def test_public_trust_center_anchor_transparency_cli(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, store = _trust_center_fixture(Path(".musicforge"), monkeypatch)
    store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    store.export_center("ptc-default")
    store.build_zip("ptc-default")
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=store)
    anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "public-trust-center",
            "--center-id",
            "ptc-default",
            "--anchor-register",
            "--anchor-publish",
            "--anchor-export",
            "--anchor-zip",
            "--anchor-verify",
            "--anchor-transparency-refresh",
            "--anchor-checkpoint-create",
            "--anchor-transparency-export",
            "--anchor-transparency-zip",
            "--anchor-transparency-verify",
            "--require-anchor-registry-current",
            "--require-anchor-published",
            "--require-anchor-not-revoked",
            "--require-anchor-transparency-current",
            "--require-anchor-checkpoint",
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
    assert payload["anchor_transparency_verification"]["status"] == "passed"
    assert payload["anchor_transparency_summary"]["status"] == "current"
    assert anchor_transparency_store.zip_path("ptc-default").exists()
    assert anchor_transparency_store.current_checkpoint_path("ptc-default").exists()

    report_out = tmp_path / "anchor-transparency-verification.json"
    verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-public-trust-center-anchor-transparency-package",
            str(anchor_transparency_store.zip_path("ptc-default")),
            "--json",
            "--strict",
            "--checkpoint",
            str(anchor_transparency_store.current_checkpoint_path("ptc-default")),
            "--anchor-registry",
            str(anchor_store.zip_path("ptc-default")),
            "--require-current-checkpoint",
            "--require-published-anchor",
            "--require-not-revoked",
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

    assert verify.returncode == 0, verify.stderr
    verified = json.loads(verify.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert verified["status"] == "passed"
    assert saved["checkpoint_hash"]


def test_public_trust_center_distribution_kit_cli(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, store = _trust_center_fixture(Path(".musicforge"), monkeypatch)
    store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    store.export_center("ptc-default")
    store.build_zip("ptc-default")
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=store)
    anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "public-trust-center",
            "--center-id",
            "ptc-default",
            "--anchor-register",
            "--anchor-publish",
            "--anchor-export",
            "--anchor-zip",
            "--anchor-verify",
            "--anchor-transparency-refresh",
            "--anchor-checkpoint-create",
            "--anchor-transparency-export",
            "--anchor-transparency-zip",
            "--anchor-transparency-verify",
            "--distribution-kit-refresh",
            "--distribution-kit-export",
            "--distribution-kit-zip",
            "--distribution-kit-verify",
            "--require-anchor-registry-current",
            "--require-anchor-published",
            "--require-anchor-not-revoked",
            "--require-anchor-transparency-current",
            "--require-anchor-checkpoint",
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
    assert payload["distribution_kit_summary"]["status"] == "ready"
    assert payload["distribution_kit_zip"]["sha256"]
    assert payload["distribution_kit_verification"]["status"] == "passed"
    kit_zip = tmp_path / ".musicforge" / "public-trust-centers" / "ptc-default" / "distribution-kit" / "public-trust-center-distribution-kit.zip"
    assert kit_zip.exists()
    assert anchor_store.zip_path("ptc-default").exists()
    assert anchor_transparency_store.zip_path("ptc-default").exists()

    report_out = tmp_path / "distribution-kit-verification.json"
    verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-public-trust-center-distribution-kit-package",
            str(kit_zip),
            "--json",
            "--strict",
            "--deep",
            "--require-current",
            "--no-require-delivery-readiness",
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

    assert verify.returncode == 0, verify.stderr
    verified = json.loads(verify.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert verified["status"] == "passed"
    assert saved["summary"]["center_id"] == "ptc-default"

    template_cmd = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "public-trust-center",
            "--center-id",
            "ptc-default",
            "--distribution-kit-acceptance-template",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert template_cmd.returncode == 0, template_cmd.stderr
    template_payload = json.loads(template_cmd.stdout)
    response = dict(template_payload["distribution_kit_acceptance_template"]["response_template"])
    response.update(
        {
            "response_id": "cli-kit-accepted-001",
            "reviewer": {"name": "CLI Receiver", "organization": "Partner Org", "role": "receiver"},
            "reviewed_at": "2026-06-15T00:00:00+00:00",
            "comments": "Distribution Kit accepted from CLI smoke.",
        }
    )
    response["response_hash"] = kit_acceptance_response_payload_hash(response)
    response_file = tmp_path / "kit-acceptance-response.json"
    response_file.write_text(json.dumps(response), encoding="utf-8")

    acceptance = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "public-trust-center",
            "--center-id",
            "ptc-default",
            "--distribution-kit-acceptance-response-file",
            str(response_file),
            "--distribution-kit-accepted-evidence-export",
            "--distribution-kit-accepted-evidence-zip",
            "--distribution-kit-accepted-evidence-verify",
            "--strict",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert acceptance.returncode == 0, acceptance.stderr
    acceptance_payload = json.loads(acceptance.stdout)
    evidence_zip = tmp_path / ".musicforge" / "public-trust-centers" / "ptc-default" / "distribution-kit" / "acceptance" / "accepted-evidence" / acceptance_payload["distribution_kit_accepted_evidence_zip"]["evidence_id"] / "accepted-evidence.zip"
    assert acceptance_payload["distribution_kit_acceptance_import"]["verification"]["status"] == "passed"
    assert acceptance_payload["distribution_kit_accepted_evidence_verification"]["status"] == "passed"
    assert evidence_zip.exists()

    evidence_report_out = tmp_path / "accepted-evidence-verification.json"
    evidence_verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-public-trust-center-distribution-kit-accepted-evidence-package",
            str(evidence_zip),
            "--json",
            "--strict",
            "--require-current",
            "--distribution-kit",
            str(kit_zip),
            "--report-out",
            str(evidence_report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert evidence_verify.returncode == 0, evidence_verify.stderr
    evidence_verified = json.loads(evidence_verify.stdout)
    evidence_saved = json.loads(evidence_report_out.read_text(encoding="utf-8"))
    assert evidence_verified["status"] == "passed"
    assert evidence_saved["summary"]["center_id"] == "ptc-default"

    response_two = dict(template_payload["distribution_kit_acceptance_template"]["response_template"])
    response_two.update(
        {
            "response_id": "cli-kit-accepted-002",
            "reviewer": {"name": "CLI Legal", "organization": "Legal Org", "role": "legal"},
            "reviewed_at": "2026-06-15T00:05:00+00:00",
            "comments": "Legal receiver accepted from CLI smoke.",
        }
    )
    response_two["response_hash"] = kit_acceptance_response_payload_hash(response_two)
    response_two_file = tmp_path / "kit-acceptance-response-two.json"
    response_two_file.write_text(json.dumps(response_two), encoding="utf-8")
    second_acceptance = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "public-trust-center",
            "--center-id",
            "ptc-default",
            "--distribution-kit-acceptance-response-file",
            str(response_two_file),
            "--distribution-kit-accepted-evidence-export",
            "--distribution-kit-accepted-evidence-zip",
            "--distribution-kit-accepted-evidence-verify",
            "--strict",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert second_acceptance.returncode == 0, second_acceptance.stderr
    policy_file = tmp_path / "acceptance-board-policy.json"
    policy_file.write_text(
        json.dumps({"requirements": {"min_accepted_count": 2, "min_accepted_organizations": 2, "required_roles": ["receiver", "legal"]}}),
        encoding="utf-8",
    )
    board = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "public-trust-center",
            "--center-id",
            "ptc-default",
            "--acceptance-board-policy-save",
            str(policy_file),
            "--acceptance-board-refresh",
            "--acceptance-board-export",
            "--acceptance-board-zip",
            "--acceptance-board-verify",
            "--strict",
            "--require-ready",
            "--require-quorum",
            "--require-no-conflicts",
            "--min-accepted-count",
            "2",
            "--min-accepted-organizations",
            "2",
            "--required-role",
            "receiver",
            "--required-role",
            "legal",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert board.returncode == 0, board.stderr
    board_payload = json.loads(board.stdout)
    board_zip = tmp_path / ".musicforge" / "public-trust-centers" / "ptc-default" / "acceptance-board" / "public-trust-center-acceptance-board.zip"
    assert board_payload["acceptance_board_summary"]["readiness"] == "ready"
    assert board_payload["acceptance_board_verification"]["status"] == "passed"
    assert board_zip.exists()

    board_report_out = tmp_path / "acceptance-board-verification.json"
    accepted_evidence_dir = tmp_path / ".musicforge" / "public-trust-centers" / "ptc-default" / "distribution-kit" / "acceptance" / "accepted-evidence"
    board_verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-public-trust-center-acceptance-board-package",
            str(board_zip),
            "--json",
            "--strict",
            "--require-ready",
            "--require-quorum",
            "--require-no-conflicts",
            "--distribution-kit",
            str(kit_zip),
            "--accepted-evidence-dir",
            str(accepted_evidence_dir),
            "--report-out",
            str(board_report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert board_verify.returncode == 0, board_verify.stderr
    board_verified = json.loads(board_verify.stdout)
    board_saved = json.loads(board_report_out.read_text(encoding="utf-8"))
    assert board_verified["status"] == "passed"
    assert board_saved["summary"]["center_id"] == "ptc-default"

    signoff_archive = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "public-trust-center",
            "--center-id",
            "ptc-default",
            "--acceptance-board-signoff",
            "--acceptance-board-signed-by",
            "CLI Reviewer",
            "--acceptance-board-signoff-reason",
            "CLI Acceptance Board quorum is ready for release.",
            "--acceptance-board-signoff-archive-export",
            "--acceptance-board-signoff-archive-zip",
            "--acceptance-board-signoff-archive-verify",
            "--strict",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert signoff_archive.returncode == 0, signoff_archive.stderr
    signoff_payload = json.loads(signoff_archive.stdout)
    archive_zip = tmp_path / ".musicforge" / "public-trust-centers" / "ptc-default" / "acceptance-board" / "signoff" / "public-trust-center-acceptance-board-signoff-archive.zip"
    assert signoff_payload["acceptance_board_signoff"]["status"] == "signed"
    assert signoff_payload["acceptance_board_signoff_archive_verification"]["status"] == "passed"
    assert archive_zip.exists()
    board_store_report = tmp_path / ".musicforge" / "public-trust-centers" / "ptc-default" / "acceptance-board" / "acceptance-board-verification-report.json"

    archive_verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-public-trust-center-acceptance-board-signoff-archive-package",
            str(archive_zip),
            "--json",
            "--strict",
            "--require-signed",
            "--require-current",
            "--require-ready",
            "--board-zip",
            str(board_zip),
            "--board-verification-report",
            str(board_store_report),
            "--distribution-kit",
            str(kit_zip),
            "--accepted-evidence-dir",
            str(accepted_evidence_dir),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert archive_verify.returncode == 0, archive_verify.stderr
    assert json.loads(archive_verify.stdout)["status"] == "passed"
