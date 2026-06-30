from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(repo_root) if not existing else f"{repo_root}{os.pathsep}{existing}"
    return subprocess.run([sys.executable, "-m", "song_agent.cli", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def _release_check_report(path: Path) -> Path:
    payload = {
        "ok": True,
        "summary": {"total": 1, "passed": 1, "failed": 0},
        "results": [{"check_id": "synthetic.passed", "status": "passed"}],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _verification_report(path: Path, *, package_type: str, target_id: str, zip_sha256: str) -> Path:
    from song_agent.releases import stable_hash

    payload = {
        "package_type": package_type,
        "status": "passed",
        "input": {"sha256": zip_sha256, "size_bytes": 1},
        "summary": {"release_id": "release-001", "target_id": target_id},
        "blockers": [],
    }
    payload["integrity_hash"] = stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_unified_command_center_cli_create_zip_verify(tmp_path: Path) -> None:
    release_check = _release_check_report(tmp_path / "release-check.json")
    create = _run_cli(
        [
            "unified-command-center",
            "--json",
            "create",
            "--center-id",
            "ucc-cli",
            "--no-require-audio-command-center",
            "--no-require-trust-operations-hub",
            "--no-require-public-trust-center",
            "--no-require-ga-readiness",
            "--require-release-check",
        ],
        tmp_path,
    )
    refresh = _run_cli(["unified-command-center", "--json", "refresh", "ucc-cli", "--release-check-report", str(release_check)], tmp_path)
    zipped = _run_cli(["unified-command-center", "--json", "zip", "ucc-cli", "--release-check-report", str(release_check)], tmp_path)
    verify = _run_cli(["unified-command-center", "--json", "verify", "ucc-cli", "--strict", "--require-ready", "--release-check-report", str(release_check)], tmp_path)

    assert create.returncode == 0, create.stderr
    assert refresh.returncode == 0, refresh.stderr
    assert json.loads(refresh.stdout)["status"] == "ready"
    assert zipped.returncode == 0, zipped.stderr
    assert Path(json.loads(zipped.stdout)["zip_path"]).exists()
    assert verify.returncode == 0, verify.stderr
    assert json.loads(verify.stdout)["status"] == "passed"


def test_unified_command_center_cli_signoff_archive_handoff(tmp_path: Path) -> None:
    release_check = _release_check_report(tmp_path / "release-check.json")
    create = _run_cli(
        [
            "unified-command-center",
            "--json",
            "create",
            "--center-id",
            "ucc-cli-signoff",
            "--no-require-audio-command-center",
            "--no-require-trust-operations-hub",
            "--no-require-public-trust-center",
            "--no-require-ga-readiness",
            "--require-release-check",
        ],
        tmp_path,
    )
    zipped = _run_cli(["unified-command-center", "--json", "zip", "ucc-cli-signoff", "--release-check-report", str(release_check)], tmp_path)
    verified = _run_cli(["unified-command-center", "--json", "verify", "ucc-cli-signoff", "--strict", "--require-ready", "--release-check-report", str(release_check)], tmp_path)
    signoff = _run_cli(["unified-command-center", "--json", "signoff", "ucc-cli-signoff", "--signed-by", "release lead", "--reason", "ready"], tmp_path)
    archive_zip = _run_cli(["unified-command-center", "--json", "archive-zip", "ucc-cli-signoff"], tmp_path)
    archive_verify = _run_cli(["unified-command-center", "--json", "verify-archive", "ucc-cli-signoff"], tmp_path)
    handoff_zip = _run_cli(["unified-command-center", "--json", "handoff-zip", "ucc-cli-signoff"], tmp_path)
    handoff_verify = _run_cli(["unified-command-center", "--json", "verify-handoff", "ucc-cli-signoff"], tmp_path)
    refresh_after_signoff = _run_cli(["unified-command-center", "--json", "refresh", "ucc-cli-signoff", "--release-check-report", str(release_check)], tmp_path)

    assert create.returncode == 0, create.stderr
    assert zipped.returncode == 0, zipped.stderr
    assert verified.returncode == 0, verified.stderr
    assert signoff.returncode == 0, signoff.stderr
    assert json.loads(signoff.stdout)["status"] == "signed"
    assert archive_zip.returncode == 0, archive_zip.stderr
    assert Path(json.loads(archive_zip.stdout)["zip_path"]).exists()
    assert archive_verify.returncode == 0, archive_verify.stderr
    assert json.loads(archive_verify.stdout)["status"] == "passed"
    assert handoff_zip.returncode == 0, handoff_zip.stderr
    assert Path(json.loads(handoff_zip.stdout)["zip_path"]).exists()
    assert handoff_verify.returncode == 0, handoff_verify.stderr
    assert json.loads(handoff_verify.stdout)["status"] == "passed"
    assert refresh_after_signoff.returncode != 0


def test_unified_command_center_cli_accepts_distribution_evidence_list(tmp_path: Path) -> None:
    import hashlib

    release_check = _release_check_report(tmp_path / "release-check.json")
    package = tmp_path / "distribution.zip"
    package.write_bytes(b"d")
    distribution_report = _verification_report(
        tmp_path / "distribution-verification.json",
        package_type="musicforge_distribution_verification",
        target_id="target-001",
        zip_sha256=hashlib.sha256(b"d").hexdigest(),
    )
    create = _run_cli(
        [
            "unified-command-center",
            "--json",
            "create",
            "--center-id",
            "ucc-cli-distribution",
            "--no-require-audio-command-center",
            "--no-require-trust-operations-hub",
            "--no-require-public-trust-center",
            "--no-require-ga-readiness",
            "--require-release-check",
            "--require-distribution-ready",
        ],
        tmp_path,
    )
    refresh = _run_cli(
        [
            "unified-command-center",
            "--json",
            "refresh",
            "ucc-cli-distribution",
            "--release-check-report",
            str(release_check),
            "--distribution-zip",
            str(package),
            "--distribution-verification-report",
            str(distribution_report),
        ],
        tmp_path,
    )

    assert create.returncode == 0, create.stderr
    assert refresh.returncode == 1, refresh.stderr
    payload = json.loads(refresh.stdout)
    assert payload["status"] == "blocked"
    assert "distribution" in payload["report"]["domain_summary"]
