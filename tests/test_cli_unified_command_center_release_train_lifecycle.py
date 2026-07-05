from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from song_agent.unified_command_center_release_train_lifecycle import UnifiedCommandCenterReleaseTrainLifecycleStore
from tests.test_unified_command_center_release_train import _train_fixture


def test_verify_unified_command_center_release_train_lifecycle_cli(tmp_path: Path) -> None:
    store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "cli lifecycle lead"})
    store.build_zip(train_id)
    store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    lifecycle = UnifiedCommandCenterReleaseTrainLifecycleStore(store)
    lifecycle.refresh_report(train_id, {"external_evidence_manifest": manifest_path})
    zipped = lifecycle.build_zip(train_id)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-unified-command-center-release-train-lifecycle-package",
            str(zipped["zip_path"]),
            "--strict",
            "--require-current-train",
            "--train-archive",
            str(store.zip_path(train_id)),
            "--train-archive-verification-report",
            str(store.verification_report_path(train_id)),
            "--train-signoff-binding",
            str(store.signoff_binding_path(train_id)),
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
