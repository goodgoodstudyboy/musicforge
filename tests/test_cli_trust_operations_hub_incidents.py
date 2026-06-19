from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_trust_operations_hub_incidents import _incident_fixture


def test_trust_operations_hub_incidents_cli_roundtrip(tmp_path: Path) -> None:
    hub_store, _incident_store, _fixture_obj, _delivery, second_distribution, report_id = _incident_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    refresh = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "trust-operations-hub-incidents",
            "--hub-id",
            "hub",
            "--refresh",
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
    assert refresh.returncode == 0, refresh.stderr
    payload = json.loads(refresh.stdout)
    incident_id = payload["incidents"][0]["incident_id"]
    component_type = payload["incidents"][0]["detected_from"]["component_type"]
    component_id = payload["incidents"][0]["detected_from"]["component_id"]

    close = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "trust-operations-hub-incidents",
            "--hub-id",
            "hub",
            "--incident-id",
            incident_id,
            "--triage",
            "--severity",
            "high",
            "--create-plan",
            "--add-evidence",
            "--evidence-file",
            str(second_distribution),
            "--component-type",
            component_type,
            "--component-id",
            component_id,
            "--verify-fix",
            "--close",
            "--reason",
            "Distribution verification evidence passed.",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-no-open-blocking",
            "--require-current-hub",
            "--hub-verification-report",
            str(hub_store.verification_report_path("hub", report_id)),
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

    assert close.returncode == 0, close.stderr
    result = json.loads(close.stdout)
    assert result["verification"]["status"] == "passed", result["verification"].get("blockers")


def test_verify_trust_operations_hub_incident_package_cli_json(tmp_path: Path) -> None:
    hub_store, incident_store, _fixture_obj, _delivery, second_distribution, report_id = _incident_fixture(tmp_path)
    incident = incident_store.list_incidents("hub")[0]
    incident_store.add_evidence("hub", incident["incident_id"], {"component_type": incident["detected_from"]["component_type"], "component_id": incident["detected_from"]["component_id"], "report": json.loads(second_distribution.read_text(encoding="utf-8"))})
    incident_store.close_incident("hub", incident["incident_id"], {"reason": "Distribution verification evidence passed.", "closed_by": "qa"})
    incident_store.export_board("hub")
    incident_store.build_zip("hub")
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-trust-operations-hub-incident-package",
            str(incident_store.zip_path("hub")),
            "--strict",
            "--require-no-open-blocking",
            "--require-current-hub",
            "--hub-verification-report",
            str(hub_store.verification_report_path("hub", report_id)),
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
    assert payload["status"] == "passed"
