from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_trust_operations_assurance_watch import _watch_fixture


def test_cli_verifies_trust_operations_assurance_watch_package(tmp_path: Path) -> None:
    _fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)
    watch_store.export_watch(queue_id)
    watch_store.build_watch_zip(queue_id)
    report_out = tmp_path / "watch-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-trust-operations-assurance-watch-package",
            str(watch_store.watch_zip_path(queue_id)),
            "--strict",
            "--require-clear",
            "--require-current",
            "--assurance-archive",
            str(payload["assurance_archive_path"]),
            "--assurance-verification-report",
            str(payload["assurance_verification_report_path"]),
            "--hub-package",
            str(payload["hub_package_path"]),
            "--hub-verification-report",
            str(payload["hub_verification_report_path"]),
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
    payload_out = json.loads(result.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload_out["status"] == "passed"
    assert saved["summary"]["queue_id"] == queue_id


def test_trust_operations_assurance_watch_cli_refresh_export_zip_verify(tmp_path: Path) -> None:
    _fixture, _assurance_store, _run_id, _watch_store, payload, _queue_id = _watch_fixture(tmp_path)
    report_out = tmp_path / "watch-command.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "trust-operations-assurance-watch",
            "--hub-id",
            "hub",
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-clear",
            "--require-current",
            "--assurance-archive",
            str(payload["assurance_archive_path"]),
            "--assurance-verification-report",
            str(payload["assurance_verification_report_path"]),
            "--hub-package",
            str(payload["hub_package_path"]),
            "--hub-verification-report",
            str(payload["hub_verification_report_path"]),
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
    payload_out = json.loads(result.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload_out["verification"]["status"] == "passed"
    assert payload_out["queue"]["status"] == "clear"
    assert payload_out["manifest"]["package_type"] == "musicforge_trust_operations_assurance_watch_manifest"
    assert payload_out["zip"]["sha256"]
    assert saved["verification"]["status"] == "passed"
