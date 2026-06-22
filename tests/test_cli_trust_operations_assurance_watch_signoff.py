from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from song_agent.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore
from song_agent.trust_operations_assurance_watch_signoff import TrustOperationsAssuranceWatchSignoffStore
from tests.test_trust_operations_assurance_watch import _watch_fixture
from tests.test_trust_operations_assurance_watch_signoff import _signoff_payload, _signed_fixture


def test_cli_verifies_trust_operations_assurance_watch_signoff_archive(tmp_path: Path) -> None:
    _fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)
    signoff_store = _signed_fixture(tmp_path, watch_store, payload, queue_id, export=True, zip_it=True)
    report_out = tmp_path / "watch-signoff-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-trust-operations-assurance-watch-signoff-archive-package",
            str(signoff_store.archive_zip_path(queue_id)),
            "--strict",
            "--require-signed",
            "--require-current",
            "--watch-package",
            str(watch_store.watch_zip_path(queue_id)),
            "--watch-verification-report",
            str(watch_store.verification_report_path(queue_id)),
            "--hub-package",
            str(payload["hub_package_path"]),
            "--hub-verification-report",
            str(payload["hub_verification_report_path"]),
            "--continuous-assurance-report",
            str(payload["assurance_verification_report_path"]),
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


def test_trust_operations_assurance_watch_signoff_cli_lifecycle(tmp_path: Path) -> None:
    _fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)
    default_watch_store = TrustOperationsAssuranceWatchStore(
        tmp_path / ".musicforge" / "trust-operations" / "assurance-watch",
        assurance_store=watch_store.assurance_store,
        hub_store=watch_store.hub_store,
    )
    refreshed = default_watch_store.refresh_queue(
        {
            "queue_id": queue_id,
            "hub_id": "hub",
            "assurance_archive_path": payload["assurance_archive_path"],
            "assurance_verification_report_path": payload["assurance_verification_report_path"],
            "hub_package_path": payload["hub_package_path"],
            "hub_verification_report_path": payload["hub_verification_report_path"],
        }
    )
    assert refreshed["queue"]["status"] == "clear"
    default_watch_store.export_watch(queue_id)
    default_watch_store.build_watch_zip(queue_id)
    default_watch_store.verify_watch_zip(queue_id, {"strict": True, "require_clear": True, "require_current": True, **payload})
    report_out = tmp_path / "watch-signoff-command.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "trust-operations-assurance-watch-signoff",
            "--queue-id",
            queue_id,
            "--refresh-closeout",
            "--sign",
            "--signed-by",
            "reviewer",
            "--reason",
            "Watch queue clear and verified.",
            "--export",
            "--zip",
            "--verify",
            "--strict",
            "--require-current",
            "--watch-package",
            str(default_watch_store.watch_zip_path(queue_id)),
            "--watch-verification-report",
            str(default_watch_store.verification_report_path(queue_id)),
            "--hub-package",
            str(payload["hub_package_path"]),
            "--hub-verification-report",
            str(payload["hub_verification_report_path"]),
            "--continuous-assurance-report",
            str(payload["assurance_verification_report_path"]),
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
    assert payload_out["closeout"]["status"] == "passed"
    assert payload_out["signoff"]["status"] == "signed"
    assert payload_out["manifest"]["package_type"] == "musicforge_trust_operations_assurance_watch_signoff_manifest"
    assert payload_out["verification"]["status"] == "passed", payload_out["verification"].get("blockers")
    assert saved["verification_summary"]["queue_id"] == queue_id
