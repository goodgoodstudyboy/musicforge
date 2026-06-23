from pathlib import Path

from song_agent import __version__
from song_agent.ga_readiness import REQUIRED_DOCS, build_ga_readiness_report, ga_readiness_integrity_ok, write_ga_readiness_report
from song_agent.ga_readiness_verifier import verify_ga_readiness_report


def _write_repo(root: Path, *, docs: bool = True) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(f'[project]\nversion = "{__version__}"\n', encoding="utf-8")
    (root / "README.md").write_text("# MusicForge\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## v{__version__}\n", encoding="utf-8")
    if docs:
        for rel in REQUIRED_DOCS:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {Path(rel).stem}\n\nLocal GA doc.\n", encoding="utf-8")


def test_ga_readiness_report_schema_and_integrity(tmp_path: Path) -> None:
    _write_repo(tmp_path)

    report = build_ga_readiness_report(repo_root=tmp_path)

    assert report["package_type"] == "musicforge_ga_readiness_report"
    assert report["app_version"] == __version__
    assert ga_readiness_integrity_ok(report)
    assert any(check["check_id"] == "ga.docs_present" for check in report["checks"])


def test_ga_readiness_blocks_missing_docs_and_manual_requirement(tmp_path: Path) -> None:
    _write_repo(tmp_path, docs=False)

    report = build_ga_readiness_report(repo_root=tmp_path, require_manual_acceptance=True)

    statuses = {check["check_id"]: check["status"] for check in report["checks"]}
    assert report["status"] == "blocked"
    assert statuses["ga.docs_present"] == "failed"
    assert statuses["ga.acceptance_manual"] == "failed"


def test_ga_readiness_write_report(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    report = build_ga_readiness_report(repo_root=tmp_path)
    out = tmp_path / "runs" / "ga.json"

    written = write_ga_readiness_report(report, out)

    assert written == out
    assert out.exists()


def test_ga_readiness_verifier_blocks_tamper_and_strict_warning(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    report = build_ga_readiness_report(repo_root=tmp_path)
    out = tmp_path / "ga.json"
    write_ga_readiness_report(report, out)

    verified = verify_ga_readiness_report(out)
    strict = verify_ga_readiness_report(out, strict=True)
    payload = out.read_text(encoding="utf-8").replace('"status": "warning"', '"status": "ready"', 1)
    out.write_text(payload, encoding="utf-8")
    tampered = verify_ga_readiness_report(out)

    assert verified["status"] == "warning"
    assert strict["status"] == "failed"
    assert tampered["status"] == "failed"


def test_ga_readiness_verifier_blocks_blocked_report(tmp_path: Path) -> None:
    _write_repo(tmp_path, docs=False)
    report = build_ga_readiness_report(repo_root=tmp_path)
    out = tmp_path / "ga.json"
    write_ga_readiness_report(report, out)

    verified = verify_ga_readiness_report(out)

    assert report["status"] == "blocked"
    assert verified["status"] == "failed"
