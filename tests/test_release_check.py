from pathlib import Path

from song_agent.release_checks import (
    ReleaseCheckReport,
    _edit_smoke,
    _final_export_smoke,
    _redact_line,
    _remote_has_token,
    _status_is_clean,
    _v38_release_zip_verifier_smoke,
    _v39_release_metadata_smoke,
    _v40_distribution_prep_smoke,
    _v41_distribution_template_packs_smoke,
    _v42_distribution_layout_contract_smoke,
    _v43_submission_workspace_smoke,
    _v44_music_acceptance_lab_smoke,
    _v45_acceptance_profiles_songbook_smoke,
    _v46_human_review_pack_smoke,
    _v47_acceptance_analytics_smoke,
    _v48_acceptance_fix_sprint_smoke,
    _version_consistency,
    print_release_check_report,
)


def test_status_is_clean_accepts_only_clean_branch_line() -> None:
    assert _status_is_clean("## master...origin/master") is True
    assert _status_is_clean("## master...origin/master [ahead 1]") is False
    assert _status_is_clean("## master...origin/master\n M README.md") is False


def test_remote_token_detection() -> None:
    assert _remote_has_token("origin https://github.com/user/repo.git") is False
    assert _remote_has_token("origin https://x-access-token:secret@github.com/user/repo.git") is True
    assert _remote_has_token("origin https://github_pat_abc123@github.com/user/repo.git") is True


def test_redact_line_masks_secret_like_values() -> None:
    line = _redact_line('Authorization: Bearer secret-token api_key="secret-value" sk-test-secret-value')

    assert "secret-token" not in line
    assert "secret-value" not in line
    assert "sk-test-secret-value" not in line


def test_version_consistency_checks_pyproject_and_changelog(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.5.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## v0.5.0\n", encoding="utf-8")
    monkeypatch.setattr("song_agent.release_checks.__version__", "0.5.0")

    ok, detail = _version_consistency(tmp_path)

    assert ok is True, detail
    assert "package=0.5.0" in detail


def test_final_export_smoke_builds_bundle(tmp_path: Path) -> None:
    ok, detail = _final_export_smoke(tmp_path)

    assert ok is True
    assert "version=v001" in detail


def test_edit_smoke_preserves_parent_and_renders_child(tmp_path: Path) -> None:
    ok, detail = _edit_smoke(tmp_path)

    assert ok is True
    assert "parent_unchanged=True" in detail


def test_v38_release_zip_verifier_smoke(tmp_path: Path) -> None:
    ok, detail = _v38_release_zip_verifier_smoke(tmp_path)

    assert ok is True, detail
    assert "external=warning" in detail


def test_v39_release_metadata_smoke(tmp_path: Path) -> None:
    ok, detail = _v39_release_metadata_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail


def test_v40_distribution_prep_smoke(tmp_path: Path) -> None:
    ok, detail = _v40_distribution_prep_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail
    assert "external=passed" in detail


def test_v41_distribution_template_packs_smoke(tmp_path: Path) -> None:
    ok, detail = _v41_distribution_template_packs_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail
    assert "template_tamper=failed" in detail
    assert "checklist_tamper=failed" in detail


def test_v42_distribution_layout_contract_smoke(tmp_path: Path) -> None:
    ok, detail = _v42_distribution_layout_contract_smoke(tmp_path)

    assert ok is True, detail
    assert "external=passed" in detail
    assert "layout_tamper=failed" in detail
    assert "artwork_path_tamper=failed" in detail


def test_v43_submission_workspace_smoke(tmp_path: Path) -> None:
    ok, detail = _v43_submission_workspace_smoke(tmp_path)

    assert ok is True, detail
    assert "external=passed" in detail
    assert "signoff_tamper=failed" in detail
    assert "target_tamper=failed" in detail


def test_v44_music_acceptance_lab_smoke(tmp_path: Path) -> None:
    ok, detail = _v44_music_acceptance_lab_smoke(tmp_path)

    assert ok is True, detail
    assert "health=passed" in detail
    assert "report_tamper=failed" in detail
    assert "signoff_integrity=failed" in detail
    assert "missing_midi=failed" in detail
    assert "signed_guard=409" in detail


def test_v45_acceptance_profiles_songbook_smoke(tmp_path: Path) -> None:
    ok, detail = _v45_acceptance_profiles_songbook_smoke(tmp_path)

    assert ok is True, detail
    assert "songs=12" in detail
    assert "diff=passed" in detail
    assert "rc=failed" in detail
    assert "incomplete_rc=failed" in detail
    assert "release_gate=409" in detail


def test_v46_human_review_pack_smoke(tmp_path: Path) -> None:
    ok, detail = _v46_human_review_pack_smoke(tmp_path)

    assert ok is True, detail
    assert "cases=12" in detail
    assert "verify=passed" in detail
    assert "needs_fix=1" in detail
    assert "reimport=201" in detail
    assert "all=release_ready_passed" in detail
    assert "pack_stale=False/False" in detail
    assert "tampered=failed" in detail
    assert "guards=400/409" in detail
    assert "song_mismatch=400" in detail


def test_v47_acceptance_analytics_smoke(tmp_path: Path) -> None:
    ok, detail = _v47_acceptance_analytics_smoke(tmp_path)

    assert ok is True, detail
    assert "heatmap=12" in detail
    assert "readiness=blocked" in detail
    assert "stale=True/409" in detail
    assert "release_gate=409/200" in detail
    assert "export_summary=blocked" in detail


def test_v48_acceptance_fix_sprint_smoke(tmp_path: Path) -> None:
    ok, detail = _v48_acceptance_fix_sprint_smoke(tmp_path)

    assert ok is True, detail
    assert "tasks=201/200" in detail
    assert "close=passed" in detail
    assert "project=closed" in detail
    assert "final=closed" in detail
    assert "gate=passed" in detail
    assert "stale_guard=409" in detail


def test_print_release_check_report(capsys) -> None:
    report = ReleaseCheckReport()
    report.add("example", True, "detail")

    print_release_check_report(report)

    output = capsys.readouterr().out
    assert "MusicForge release-check" in output
    assert "example: ok" in output
