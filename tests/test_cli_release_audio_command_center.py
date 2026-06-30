from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.helpers_release_audio_command_center import append_untrusted_entry, command_center_fixture


def _evidence_args(evidence: dict) -> list[str]:
    return [
        "--certification-zip",
        str(evidence["certification"]["zip"]),
        "--certification-verification-report",
        str(evidence["certification"]["verification_report"]),
        "--timeline-zip",
        str(evidence["timeline"]["zip"]),
        "--timeline-verification-report",
        str(evidence["timeline"]["verification_report"]),
        "--regression-zip",
        str(evidence["regression"]["zip"]),
        "--regression-verification-report",
        str(evidence["regression"]["verification_report"]),
        "--baseline-registry-zip",
        str(evidence["baseline_governance"]["zip"]),
        "--baseline-registry-verification-report",
        str(evidence["baseline_governance"]["verification_report"]),
        "--regression-response-zip",
        str(evidence["regression_response"]["zip"]),
        "--regression-response-verification-report",
        str(evidence["regression_response"]["verification_report"]),
        "--observatory-zip",
        str(evidence["observatory"]["zip"]),
        "--observatory-verification-report",
        str(evidence["observatory"]["verification_report"]),
        "--action-queue-zip",
        str(evidence["action_queue"]["zip"]),
        "--action-queue-verification-report",
        str(evidence["action_queue"]["verification_report"]),
        "--action-queue-signoff-archive",
        str(evidence["action_queue_signoff"]["zip"]),
        "--action-queue-signoff-verification-report",
        str(evidence["action_queue_signoff"]["verification_report"]),
        "--evidence-root",
        str(evidence["evidence_root"]),
    ]


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(repo_root) if not existing else f"{repo_root}{os.pathsep}{existing}"
    return subprocess.run([sys.executable, "-m", "song_agent.cli", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_release_audio_command_center_cli_reports_runtime_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with command_center_fixture() as fixture:
        result = _run_cli(["release-audio-command-center", "--json", "refresh", fixture.release_id, *_evidence_args(fixture.evidence)], tmp_path)
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "passed"

        inventory_result = _run_cli(["release-audio-command-center", "--json", "inventory", fixture.release_id], tmp_path)
        assert inventory_result.returncode == 0, inventory_result.stderr
        inventory = json.loads(inventory_result.stdout)["inventory"]
        action_queue = next(row for row in inventory["components"] if row["component_key"] == "action_queue")
        assert action_queue["fingerprint"]["runtime_verification_status"] == "passed"

        append_untrusted_entry(fixture.evidence["action_queue"]["zip"])
        failed = _run_cli(["release-audio-command-center", "--json", "refresh", fixture.release_id, *_evidence_args(fixture.evidence)], tmp_path)
        assert failed.returncode == 1
        failed_payload = json.loads(failed.stdout)
        assert failed_payload["status"] == "failed"
        assert "acc-gap-action_queue" in failed_payload["report"]["blockers"]
