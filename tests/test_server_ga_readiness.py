from pathlib import Path

from song_agent import __version__
from song_agent.ga_readiness import REQUIRED_DOCS
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def _write_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text(f'[project]\nversion = "{__version__}"\n', encoding="utf-8")
    (root / "README.md").write_text("# MusicForge\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## v{__version__}\n", encoding="utf-8")
    for rel in REQUIRED_DOCS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {Path(rel).stem}\n", encoding="utf-8")


def test_server_ga_readiness_routes(tmp_path: Path, monkeypatch) -> None:
    _write_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(server, "GET", "/api/ga")
        assert status == 200
        assert data["report"]["package_type"] == "musicforge_ga_readiness_report"

        docs_status, docs = request_json(server, "GET", "/api/docs/index")
        assert docs_status == 200
        assert docs["summary"]["present_count"] == len(REQUIRED_DOCS)

        check_status, checked = request_json(server, "POST", "/api/ga/check", {"require_manual_acceptance": True})
        assert check_status == 200
        assert checked["report"]["status"] == "blocked"
        assert (tmp_path / "runs" / "ga-readiness" / "ga-readiness-report.json").exists()
    finally:
        stop_test_server(server)

