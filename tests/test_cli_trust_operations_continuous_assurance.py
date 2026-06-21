from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_trust_operations_continuous_assurance import _assurance_fixture


def test_cli_verifies_trust_operations_assurance_archive(tmp_path: Path) -> None:
    fixture = _assurance_fixture(tmp_path)
    store = fixture.assurance_store
    run_id = store.refresh_run("hub", fixture.payload)["run"]["run_id"]
    store.export_archive(run_id)
    store.build_archive_zip(run_id)
    report_out = tmp_path / "assurance-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-trust-operations-assurance-package",
            str(store.archive_zip_path(run_id)),
            "--strict",
            "--require-passed",
            "--require-current",
            "--hub-package",
            str(fixture.payload["hub_package_path"]),
            "--hub-verification-report",
            str(fixture.payload["hub_verification_report_path"]),
            "--control-signoff-archive",
            str(fixture.payload["control_signoff_archive_path"]),
            "--control-signoff-verification-report",
            str(fixture.payload["control_signoff_verification_report_path"]),
            "--control-package",
            str(fixture.payload["control_package_path"]),
            "--control-verification-report",
            str(fixture.payload["control_verification_report_path"]),
            "--incident-board-package",
            str(fixture.payload["incident_board_package_path"]),
            "--incident-board-verification-report",
            str(fixture.payload["incident_board_verification_report_path"]),
            "--incident-knowledge-package",
            str(fixture.payload["incident_knowledge_package_path"]),
            "--incident-knowledge-verification-report",
            str(fixture.payload["incident_knowledge_verification_report_path"]),
            "--release-verification",
            str(fixture.assurance_verifier_payload["release_verification_paths"][0]),
            "--distribution-verification",
            str(fixture.assurance_verifier_payload["distribution_verification_paths"][0]),
            "--distribution-verification",
            str(fixture.assurance_verifier_payload["distribution_verification_paths"][1]),
            "--submission-verification",
            str(fixture.assurance_verifier_payload["submission_verification_paths"][0]),
            "--submission-evidence-verification",
            str(fixture.assurance_verifier_payload["submission_evidence_verification_paths"][0]),
            "--release-operations-verification",
            str(fixture.assurance_verifier_payload["release_operations_verification_paths"][0]),
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
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["run_id"] == run_id


def test_trust_operations_assurance_cli_refresh_export_zip_verify(tmp_path: Path) -> None:
    fixture = _assurance_fixture(tmp_path)
    report_out = tmp_path / "assurance-command.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "trust-operations-assurance",
            "--hub-id",
            "hub",
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-passed",
            "--require-current",
            "--hub-package",
            str(fixture.payload["hub_package_path"]),
            "--hub-verification-report",
            str(fixture.payload["hub_verification_report_path"]),
            "--control-signoff-archive",
            str(fixture.payload["control_signoff_archive_path"]),
            "--control-signoff-verification-report",
            str(fixture.payload["control_signoff_verification_report_path"]),
            "--control-package",
            str(fixture.payload["control_package_path"]),
            "--control-verification-report",
            str(fixture.payload["control_verification_report_path"]),
            "--incident-board-package",
            str(fixture.payload["incident_board_package_path"]),
            "--incident-board-verification-report",
            str(fixture.payload["incident_board_verification_report_path"]),
            "--incident-knowledge-package",
            str(fixture.payload["incident_knowledge_package_path"]),
            "--incident-knowledge-verification-report",
            str(fixture.payload["incident_knowledge_verification_report_path"]),
            "--release-verification",
            str(fixture.assurance_verifier_payload["release_verification_paths"][0]),
            "--distribution-verification",
            str(fixture.assurance_verifier_payload["distribution_verification_paths"][0]),
            "--distribution-verification",
            str(fixture.assurance_verifier_payload["distribution_verification_paths"][1]),
            "--submission-verification",
            str(fixture.assurance_verifier_payload["submission_verification_paths"][0]),
            "--submission-evidence-verification",
            str(fixture.assurance_verifier_payload["submission_evidence_verification_paths"][0]),
            "--release-operations-verification",
            str(fixture.assurance_verifier_payload["release_operations_verification_paths"][0]),
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
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["verification"]["status"] == "passed"
    assert payload["manifest"]["package_type"] == "musicforge_trust_operations_continuous_assurance_manifest"
    assert payload["zip"]["sha256"]
    assert payload["zip"]["size_bytes"] > 0
    assert saved["verification"]["status"] == "passed"
    assert saved["verification_summary"]["run_id"] == payload["run"]["run_id"]
