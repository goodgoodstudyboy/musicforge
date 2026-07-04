from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_unified_command_center_release_train import _train_fixture


def test_verify_unified_command_center_release_train_cli(tmp_path: Path) -> None:
    store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "cli train lead"})
    zipped = store.build_zip(train_id)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-unified-command-center-release-train-package",
            str(zipped["zip_path"]),
            "--strict",
            "--require-go",
            "--require-signed",
            "--external-evidence-manifest",
            str(manifest_path),
            "--json",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "passed", payload.get("blockers")
