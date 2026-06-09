from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "song_agent.cli", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)


def test_release_check_cli_list_json() -> None:
    completed = _run_cli(["release-check", "--profile", "latest", "--list", "--json"])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    ids = {item["check_id"] for item in payload["checks"]}
    assert "v74.attestation_portal_smoke" in ids
    assert "v75.release_check_matrix_smoke" in ids


def test_release_check_cli_only_json_report_out(tmp_path: Path) -> None:
    report_out = tmp_path / "release-check.json"
    timing_out = tmp_path / "timing.json"
    completed = _run_cli(
        [
            "release-check",
            "--only",
            "v75.release_check_matrix_smoke",
            "--json",
            "--report-out",
            str(report_out),
            "--timing-out",
            str(timing_out),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    written = json.loads(report_out.read_text(encoding="utf-8"))
    timing = json.loads(timing_out.read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == 1
    assert written["results"][0]["check_id"] == "v75.release_check_matrix_smoke"
    assert timing["results"][0]["check_id"] == "v75.release_check_matrix_smoke"


def test_release_check_cli_group_timing(tmp_path: Path) -> None:
    timing_out = tmp_path / "portal-timing.json"
    completed = _run_cli(["release-check", "--profile", "latest", "--group", "portal", "--list", "--json", "--timing-out", str(timing_out)])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert {item["check_id"] for item in payload["checks"]} == {"v74.attestation_portal_smoke"}

