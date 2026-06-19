from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from song_agent.trust_operations_hub import TrustOperationsHubStore
from tests.test_trust_operations_hub import _delivery_fixture, _fixture


def test_trust_operations_hub_runbook_cli_create_run_export_zip_verify(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    delivery = _delivery_fixture(tmp_path)
    hub_store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub_store.create_hub({"hub_id": "hub"})
    report_id = hub_store.refresh_report("hub", {**fixture.payload, **delivery.payload})["hub_report"]["report_id"]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "trust-operations-hub-runbook",
            "--hub-id",
            "hub",
            "--report-id",
            report_id,
            "--runbook-id",
            "runbook-1",
            "--create",
            "--run-safe",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-completed",
            "--require-no-blocked",
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
    assert payload["result"]["summary"]["completed_count"] == 3
    assert payload["verification"]["status"] == "passed", payload["verification"].get("blockers")


def test_verify_trust_operations_hub_runbook_cli_json_report_out(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    hub_store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub_store.create_hub({"hub_id": "hub"})
    report_id = hub_store.refresh_report("hub", fixture.payload)["hub_report"]["report_id"]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    create = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "trust-operations-hub-runbook",
            "--hub-id",
            "hub",
            "--report-id",
            report_id,
            "--runbook-id",
            "runbook-2",
            "--create",
            "--run-safe",
            "--export",
            "--zip",
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
    assert create.returncode == 0, create.stderr
    report_out = tmp_path / "runbook-verification.json"
    verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-trust-operations-hub-runbook-package",
            str(tmp_path / ".musicforge" / "trust-operations-runbooks" / "hubs" / "hub" / "runbooks" / "runbook-2" / "trust-operations-hub-runbook.zip"),
            "--strict",
            "--require-completed",
            "--require-no-blocked",
            "--report-out",
            str(report_out),
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

    assert verify.returncode == 0, verify.stderr
    payload = json.loads(verify.stdout)
    written = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert written["package_type"] == "musicforge_trust_operations_hub_runbook_verification"
