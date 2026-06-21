from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_trust_operations_controls import _control_payload, _controls_fixture


def test_trust_operations_controls_cli_roundtrip(tmp_path: Path) -> None:
    hub_store, incident_store, knowledge_store, _fixture, _delivery, _second_distribution, report_id = _controls_fixture(tmp_path)
    payload = _control_payload(hub_store, incident_store, knowledge_store, report_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    command = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "trust-operations-controls",
            "--hub-id",
            "hub",
            "--refresh-catalog",
            "--create-policy",
            "--policy-id",
            "toc-policy-000001",
            "--assess",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-policy-passed",
            "--hub-package",
            str(payload["hub_package_path"]),
            "--hub-verification-report",
            str(payload["hub_verification_report_path"]),
            "--incident-board-package",
            str(payload["incident_board_package_path"]),
            "--incident-board-verification-report",
            str(payload["incident_board_verification_report_path"]),
            "--incident-knowledge-package",
            str(payload["incident_knowledge_package_path"]),
            "--incident-knowledge-verification-report",
            str(payload["incident_knowledge_verification_report_path"]),
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

    assert command.returncode == 0, command.stderr
    payload = json.loads(command.stdout)
    assert payload["verification"]["status"] == "passed", payload["verification"].get("blockers")
