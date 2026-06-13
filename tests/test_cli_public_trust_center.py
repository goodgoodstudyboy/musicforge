from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_public_trust_center import _trust_center_fixture


def test_public_trust_center_cli_export_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, store = _trust_center_fixture(Path(".musicforge"), monkeypatch)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "public-trust-center",
            "--center-id",
            "ptc-default",
            "--portfolio-id",
            portfolio_id,
            "--refresh",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-registry-current",
            "--require-portal-current",
            "--require-transparency-current",
            "--require-acknowledgement-current",
            "--no-require-release-signoff",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["status"] == "passed"
    assert payload["zip"]["sha256"]
    assert payload["verification"]["status"] == "passed"
    assert store.zip_path("ptc-default").exists()


def test_verify_public_trust_center_cli_json_report_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, store = _trust_center_fixture(Path(".musicforge"), monkeypatch)
    store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    store.export_center("ptc-default")
    store.build_zip("ptc-default")
    report_out = tmp_path / "public-trust-center-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-public-trust-center-package",
            str(store.zip_path("ptc-default")),
            "--json",
            "--strict",
            "--require-registry-current",
            "--require-portal-current",
            "--require-transparency-current",
            "--require-acknowledgement-current",
            "--report-out",
            str(report_out),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["summary"]["center_id"] == "ptc-default"
