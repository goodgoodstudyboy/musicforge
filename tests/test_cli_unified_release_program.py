from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from song_agent.unified_release_program import write_external_evidence_manifest
from tests.test_unified_release_program import _signed_handoff_fixture


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "song_agent.cli", *args],
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
        text=True,
        capture_output=True,
        check=False,
    )


def _program_manifest(tmp_path: Path, program_id: str, item_id: str, handoff: dict) -> Path:
    manifest_path = tmp_path / f"{program_id}-external-evidence.json"
    write_external_evidence_manifest(
        manifest_path,
        program_id=program_id,
        items=[
            {
                "item_id": item_id,
                "train_id": handoff["train_id"],
                "handoff_id": handoff["handoff_id"],
                "handoff_zip": str(handoff["handoff_zip"]),
                "handoff_verification_report": str(handoff["handoff_verification_report"]),
                "handoff_signoff_binding": str(handoff["handoff_signoff_binding"]),
            }
        ],
    )
    return manifest_path


def test_unified_release_program_cli_lifecycle(tmp_path: Path) -> None:
    handoff = _signed_handoff_fixture(tmp_path)
    manifest_path = _program_manifest(tmp_path, "urp-cli", "train-a", handoff)

    create = _run_cli(["unified-release-program", "--json", "create", "--program-id", "urp-cli", "--name", "CLI Program"], tmp_path)
    add = _run_cli(
        [
            "unified-release-program",
            "--json",
            "add-train",
            "urp-cli",
            "--item-id",
            "train-a",
            "--train-id",
            handoff["train_id"],
            "--handoff-id",
            handoff["handoff_id"],
            "--handoff-zip",
            str(handoff["handoff_zip"]),
            "--handoff-verification-report",
            str(handoff["handoff_verification_report"]),
            "--handoff-signoff-binding",
            str(handoff["handoff_signoff_binding"]),
        ],
        tmp_path,
    )
    refresh = _run_cli(["unified-release-program", "--json", "refresh", "urp-cli", "--external-evidence-manifest", str(manifest_path)], tmp_path)
    signoff = _run_cli(["unified-release-program", "--json", "signoff", "urp-cli", "--external-evidence-manifest", str(manifest_path), "--signed-by", "program owner"], tmp_path)
    zipped = _run_cli(["unified-release-program", "--json", "zip", "urp-cli"], tmp_path)
    verify = _run_cli(
        [
            "unified-release-program",
            "--json",
            "verify",
            "urp-cli",
            "--strict",
            "--require-current",
            "--require-signed",
            "--external-evidence-manifest",
            str(manifest_path),
        ],
        tmp_path,
    )

    assert create.returncode == 0, create.stderr
    assert add.returncode == 0, add.stderr
    assert refresh.returncode == 0, refresh.stderr
    assert json.loads(refresh.stdout)["report"]["status"] == "ready"
    assert signoff.returncode == 0, signoff.stderr
    assert json.loads(signoff.stdout)["signoff"]["status"] == "signed"
    assert zipped.returncode == 0, zipped.stderr
    assert verify.returncode == 0, verify.stderr
    assert json.loads(verify.stdout)["verification"]["status"] == "passed"


def test_unified_release_program_cli_deferred_only_signoff_fails(tmp_path: Path) -> None:
    create = _run_cli(["unified-release-program", "--json", "create", "--program-id", "urp-deferred"], tmp_path)
    add = _run_cli(["unified-release-program", "--json", "add-train", "urp-deferred", "--item-id", "train-deferred", "--train-id", "uct-deferred", "--handoff-id", "rth-deferred", "--type", "deferred"], tmp_path)
    refresh = _run_cli(["unified-release-program", "--json", "refresh", "urp-deferred"], tmp_path)
    signoff = _run_cli(["unified-release-program", "--json", "signoff", "urp-deferred", "--signed-by", "program owner"], tmp_path)

    assert create.returncode == 0, create.stderr
    assert add.returncode == 0, add.stderr
    assert refresh.returncode == 0, refresh.stderr
    assert json.loads(refresh.stdout)["report"]["status"] == "blocked"
    assert signoff.returncode == 1
    assert "must be ready" in signoff.stderr
