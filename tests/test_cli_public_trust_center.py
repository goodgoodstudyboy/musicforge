from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_public_trust_center import _trust_center_fixture
from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore
from song_agent.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore


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
