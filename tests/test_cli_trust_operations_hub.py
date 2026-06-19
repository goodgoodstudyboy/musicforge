from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_trust_operations_hub import _copy_delivery_report, _delivery_fixture, _fixture

from song_agent.trust_operations_hub import TrustOperationsHubStore


def test_verify_trust_operations_hub_cli_json_report_out(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub = store.create_hub({"hub_id": "hub"})
    report_id = store.refresh_report(hub["hub_id"], fixture.payload)["hub_report"]["report_id"]
    store.export_report("hub", report_id)
    store.build_zip("hub", report_id)
    store.verify_zip("hub", report_id, {**fixture.verify_payload, "strict": True, "require_ready": True, "require_current": True, "require_publication_monitoring_clean": True})
    store.signoff("hub", report_id, {"signed_by": "cli", "reason": "Trust hub CLI accepted."})
    report_out = tmp_path / "hub-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-trust-operations-hub-package",
            str(store.zip_path("hub", report_id)),
            "--json",
            "--strict",
            "--require-ready",
            "--require-current",
            "--require-signed",
            "--require-publication-monitoring-clean",
            "--publication-channel-state",
            str(fixture.channel_state_path),
            "--public-trust-center-verification",
            str(fixture.ptc_verification_path),
            "--publication-monitoring-verification",
            str(fixture.monitoring_verification_path),
            "--hub-signoff",
            str(store.signoff_path("hub")),
            "--hub-verification-report",
            str(store.verification_report_path("hub", report_id)),
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["hub_id"] == "hub"


def test_trust_operations_hub_cli_create_refresh_export_zip_verify(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "trust-operations-hub",
            "--hub-id",
            "hub",
            "--create",
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-ready",
            "--require-current",
            "--require-publication-monitoring-clean",
            "--publication-channel-state",
            str(fixture.channel_state_path),
            "--public-trust-center-verification",
            str(fixture.ptc_verification_path),
            "--publication-monitoring-verification",
            str(fixture.monitoring_verification_path),
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["verification"]["status"] == "passed"
    assert payload["zip"]["sha256"]


def test_verify_trust_operations_hub_cli_accepts_repeated_delivery_reports(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    delivery = _delivery_fixture(tmp_path)
    second_distribution = _copy_delivery_report(delivery.verify_payload["distribution_verification_path"], tmp_path / "target-002-verification.json", "target-002", "8" * 64)
    store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    store.create_hub({"hub_id": "hub"})
    report_id = store.refresh_report(
        "hub",
        {
            **fixture.payload,
            **delivery.payload,
            "distribution_verification_paths": [delivery.verify_payload["distribution_verification_path"], second_distribution],
        },
    )["hub_report"]["report_id"]
    store.export_report("hub", report_id)
    store.build_zip("hub", report_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-trust-operations-hub-package",
            str(store.zip_path("hub", report_id)),
            "--json",
            "--strict",
            "--require-delivery-ready",
            "--release-verification",
            str(delivery.verify_payload["release_verification_path"]),
            "--distribution-verification",
            str(delivery.verify_payload["distribution_verification_path"]),
            "--distribution-verification",
            str(second_distribution),
            "--submission-verification",
            str(delivery.verify_payload["submission_verification_path"]),
            "--submission-evidence-verification",
            str(delivery.verify_payload["submission_evidence_verification_path"]),
            "--release-operations-verification",
            str(delivery.verify_payload["release_operations_verification_path"]),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
