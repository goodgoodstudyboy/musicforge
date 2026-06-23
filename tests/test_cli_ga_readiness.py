import json
import os
import subprocess
import sys
from pathlib import Path

from song_agent import __version__
from song_agent.ga_readiness import REQUIRED_DOCS


def _write_repo(root: Path, *, docs: bool = True) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(f'[project]\nversion = "{__version__}"\n', encoding="utf-8")
    (root / "README.md").write_text("# MusicForge\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## v{__version__}\n", encoding="utf-8")
    if docs:
        for rel in REQUIRED_DOCS:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {Path(rel).stem}\n", encoding="utf-8")


def test_ga_check_cli_json_report_out(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    out = tmp_path / "ga-report.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get("PYTHONPATH", "")}

    result = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "ga-check", "--json", "--report-out", str(out)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert report["package_type"] == "musicforge_ga_readiness_report"
    assert saved["integrity_hash"] == report["integrity_hash"]


def test_ga_check_cli_blocks_missing_manual_acceptance(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get("PYTHONPATH", "")}

    result = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "ga-check", "--require-manual-acceptance", "--json"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "blocked"


def test_verify_ga_readiness_report_cli_json(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    out = tmp_path / "ga-report.json"
    verify_out = tmp_path / "ga-verify.json"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "ga-check", "--json", "--report-out", str(out)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )

    result = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-ga-readiness-report", str(out), "--json", "--report-out", str(verify_out)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    saved = json.loads(verify_out.read_text(encoding="utf-8"))
    assert report["package_type"] == "musicforge_ga_readiness_verification_report"
    assert saved["integrity_hash"] == report["integrity_hash"]
