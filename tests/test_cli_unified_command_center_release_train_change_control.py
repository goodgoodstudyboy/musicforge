from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from song_agent.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore
from tests.test_unified_command_center_release_train import _train_fixture


def test_verify_unified_command_center_release_train_change_control_cli(tmp_path: Path) -> None:
    store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "cli original"})
    store.build_zip(train_id)
    store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(store)
    request = change_store.create_request(train_id, {"external_evidence_manifest": manifest_path, "change": ["refresh"]})
    change_store.approve_request(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})
    change_store.reset_train_signoff(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})
    store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "cli successor"})
    store.build_zip(train_id)
    store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    zipped = change_store.build_zip(train_id)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-unified-command-center-release-train-change-control-package",
            str(zipped["zip_path"]),
            "--strict",
            "--require-reset-applied",
            "--require-current-train",
            "--train-archive",
            str(store.zip_path(train_id)),
            "--train-archive-verification-report",
            str(store.verification_report_path(train_id)),
            "--train-signoff-binding",
            str(store.signoff_binding_path(train_id)),
            "--external-evidence-manifest",
            str(manifest_path),
            "--reset-proof",
            str(change_store.reset_proof_path(train_id, request["change_request_id"])),
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
