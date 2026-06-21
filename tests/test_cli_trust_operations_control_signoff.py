from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.test_trust_operations_control_signoff import _signoff_fixture
from tests.test_trust_operations_controls import _controls_fixture


def test_cli_verifies_trust_operations_control_signoff_archive(tmp_path: Path) -> None:
    hub_store, incident_store, knowledge_store, _fixture, _delivery, _second_distribution, report_id = _controls_fixture(tmp_path)
    control_store, signoff_store, assessment_id, payload = _signoff_fixture(tmp_path, hub_store, incident_store, knowledge_store, report_id)
    signoff_store.sign("hub", assessment_id, payload)
    signoff_store.export_archive("hub", payload)
    signoff_store.build_archive_zip("hub")

    command = [
        sys.executable,
        "-m",
        "song_agent.cli",
        "verify-trust-operations-control-signoff-archive-package",
        str(signoff_store.archive_zip_path("hub")),
        "--strict",
        "--require-signed",
        "--require-current",
        "--control-package",
        str(control_store.zip_path("hub", assessment_id)),
        "--control-verification-report",
        str(control_store.verification_report_path("hub", assessment_id)),
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
    ]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr or result.stdout
    assert '"status": "passed"' in result.stdout
