from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_trust_operations_incident_knowledge import _closed_incident_fixture


def test_trust_operations_incident_knowledge_cli_roundtrip(tmp_path: Path) -> None:
    hub_store, _incident_store, _fixture_obj, _delivery, _second_distribution, report_id = _closed_incident_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    command = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "trust-operations-incident-knowledge",
            "--hub-id",
            "hub",
            "--refresh",
            "--create-guard",
            "--run-all-guards",
            "--refresh-recurrence",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-guards-passed",
            "--require-no-open-recurrence",
            "--incident-board-package",
            str(tmp_path / ".musicforge" / "trust-operations-incidents" / "hub" / "trust-operations-incident-board.zip"),
            "--incident-board-verification-report",
            str(tmp_path / ".musicforge" / "trust-operations-incidents" / "hub" / "trust-operations-incident-verification-report.json"),
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

    assert command.returncode == 0, command.stderr
    payload = json.loads(command.stdout)
    assert payload["verification"]["status"] == "passed", payload["verification"].get("blockers")
    assert payload["guard_runs"]["summary"]["passed_count"] == 1

    verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-trust-operations-incident-knowledge-package",
            str(tmp_path / ".musicforge" / "trust-operations-knowledge" / "hub" / "trust-operations-incident-knowledge.zip"),
            "--strict",
            "--require-guards-passed",
            "--require-no-open-recurrence",
            "--incident-board-package",
            str(tmp_path / ".musicforge" / "trust-operations-incidents" / "hub" / "trust-operations-incident-board.zip"),
            "--incident-board-verification-report",
            str(tmp_path / ".musicforge" / "trust-operations-incidents" / "hub" / "trust-operations-incident-verification-report.json"),
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

    assert verify.returncode == 0, verify.stderr
    report = json.loads(verify.stdout)
    assert report["status"] == "passed", report.get("blockers")
