from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from song_agent.trust_operations_final_readiness import TrustOperationsFinalReadinessStore
from tests.test_trust_operations_final_readiness import _final_fixture


def test_cli_verifies_trust_operations_final_handoff_package(tmp_path: Path) -> None:
    _fixture, _watch_store, _signoff_store, source, _queue_id = _final_fixture(tmp_path)
    store = TrustOperationsFinalReadinessStore(tmp_path / ".musicforge" / "trust-operations-final-readiness")
    store.refresh_report(source)
    store.create_certificate()
    store.sign({"signed_by": "reviewer", "role": "owner", "reason": "Final handoff is verified."})
    store.export_handoff(source)
    store.build_handoff_zip()
    report_out = tmp_path / "final-handoff-verification.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-trust-operations-final-handoff-package",
            str(store.handoff_zip_path()),
            "--strict",
            "--require-signed",
            "--require-current",
            "--hub-package",
            str(source["hub_package_path"]),
            "--hub-verification-report",
            str(source["hub_verification_report_path"]),
            "--continuous-assurance-archive",
            str(source["continuous_assurance_archive_path"]),
            "--continuous-assurance-verification-report",
            str(source["continuous_assurance_verification_report_path"]),
            "--assurance-watch-package",
            str(source["assurance_watch_package_path"]),
            "--assurance-watch-verification-report",
            str(source["assurance_watch_verification_report_path"]),
            "--assurance-watch-signoff-archive",
            str(source["assurance_watch_signoff_archive_path"]),
            "--assurance-watch-signoff-verification-report",
            str(source["assurance_watch_signoff_verification_report_path"]),
            "--control-package",
            str(source["control_package_path"]),
            "--control-verification-report",
            str(source["control_verification_report_path"]),
            "--control-signoff-archive",
            str(source["control_signoff_archive_path"]),
            "--control-signoff-verification-report",
            str(source["control_signoff_verification_report_path"]),
            "--incident-board-package",
            str(source["incident_board_package_path"]),
            "--incident-board-verification-report",
            str(source["incident_board_verification_report_path"]),
            "--incident-knowledge-package",
            str(source["incident_knowledge_package_path"]),
            "--incident-knowledge-verification-report",
            str(source["incident_knowledge_verification_report_path"]),
            "--release-verification",
            str(source["release_verification_paths"][0]),
            "--distribution-verification",
            str(source["distribution_verification_paths"][0]),
            "--distribution-verification",
            str(source["distribution_verification_paths"][1]),
            "--submission-verification",
            str(source["submission_verification_paths"][0]),
            "--submission-evidence-verification",
            str(source["submission_evidence_verification_paths"][0]),
            "--release-operations-verification",
            str(source["release_operations_verification_paths"][0]),
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
    assert payload_out["status"] == "passed", payload_out.get("blockers")
    assert saved["status"] == "passed"
    assert saved["summary"]["signoff_id"]
