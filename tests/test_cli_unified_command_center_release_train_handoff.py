from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_unified_command_center_release_train_handoff import _handoff_fixture


def test_verify_unified_command_center_release_train_handoff_cli(tmp_path: Path) -> None:
    handoff_store, handoff_id, train_store, change_store, lifecycle_store, train_id, manifest_path, payload = _handoff_fixture(tmp_path)
    handoff_store.signoff(train_id, handoff_id, {**payload, "signed_by": "handoff cli lead"})
    zipped = handoff_store.build_zip(train_id, handoff_id)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-unified-command-center-release-train-handoff-package",
            str(zipped["zip_path"]),
            "--strict",
            "--require-current",
            "--require-lifecycle",
            "--require-signed",
            "--train-archive",
            str(train_store.zip_path(train_id)),
            "--train-archive-verification-report",
            str(train_store.verification_report_path(train_id)),
            "--train-signoff-binding",
            str(train_store.signoff_binding_path(train_id)),
            "--external-evidence-manifest",
            str(manifest_path),
            "--change-control-zip",
            str(change_store.zip_path(train_id)),
            "--change-control-verification-report",
            str(change_store.verification_report_path(train_id)),
            "--reset-proof",
            str(payload["reset_proofs"][0]),
            "--lifecycle-zip",
            str(lifecycle_store.zip_path(train_id)),
            "--lifecycle-verification-report",
            str(lifecycle_store.verification_report_path(train_id)),
            "--handoff-signoff-binding",
            str(handoff_store.signoff_binding_path(train_id, handoff_id)),
            "--json",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "passed", report.get("blockers")
