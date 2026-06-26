from pathlib import Path

from song_agent import __version__
from song_agent.ga_readiness import REQUIRED_DOCS, build_ga_readiness_report, ga_readiness_integrity_hash, ga_readiness_integrity_ok, write_ga_readiness_report
from song_agent.ga_readiness_verifier import verify_ga_readiness_report
from song_agent.music_acceptance import AcceptanceStore
from song_agent.projectio import read_json, write_json
from tests.test_audio_campaign_remediation import _complete_first_fix_sprint, _needs_fix_release_campaign
from tests.test_trust_operations_final_readiness import _final_fixture
from tests.test_server_releases import start_test_server, stop_test_server
from song_agent.trust_operations_final_readiness import TrustOperationsFinalReadinessStore


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


def test_ga_readiness_verifier_requires_external_manual_acceptance_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_repo(tmp_path)
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = store.create_suite({"min_rating": 3})
    case = store.add_case(suite.suite_id, {"request": {"title": "GA Manual", "language": "English", "style": "pop", "theme": "ga", "duration_seconds": 30}})
    store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
    store.run_health(suite.suite_id, case.case_id)
    store.write_review(
        suite.suite_id,
        case.case_id,
        {"rating": 4, "status": "accepted", "playback_confirmed": True, "notes": "Manual listening review confirms this GA fixture is acceptable.", "audio_mode": "midi", "review_mode": "manual"},
    )
    acceptance_report = store.build_report(suite.suite_id)
    assert acceptance_report["status"] == "passed"
    ga_report = build_ga_readiness_report(repo_root=tmp_path, require_manual_acceptance=True)
    out = tmp_path / "ga.json"
    write_ga_readiness_report(ga_report, out)

    missing_external = verify_ga_readiness_report(out, strict=True, require_manual_acceptance=True)
    with_external = verify_ga_readiness_report(out, require_manual_acceptance=True, manual_acceptance_report_path=store.report_path(suite.suite_id))

    assert _check_status(missing_external, "ga_readiness_manual_acceptance_report_required") == "failed"
    assert _check_status(with_external, "ga_readiness_manual_acceptance_report_ga_binding") == "passed"


def test_ga_readiness_verifier_rejects_full_resigned_manual_check_without_external_report(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    report = build_ga_readiness_report(repo_root=tmp_path, require_manual_acceptance=True)
    for check in report["checks"]:
        if check["check_id"] == "ga.acceptance_manual":
            check["status"] = "passed"
            check["severity"] = "info"
            check["detail"] = {"status": "passed", "manual_ready_count": 1, "latest": {"suite_id": "suite-000001", "status": "passed", "manual_accepted_count": 1}}
    report["status"] = "ready"
    report["summary"]["acceptance_status"] = "passed"
    report["integrity_hash"] = ga_readiness_integrity_hash(report)
    out = tmp_path / "ga-forged.json"
    write_json(out, report)

    verified = verify_ga_readiness_report(out, strict=True, require_ready=True, require_manual_acceptance=True)

    assert _check_status(verified, "ga_readiness_integrity") == "passed"
    assert _check_status(verified, "ga_readiness_require_ready") == "passed"
    assert _check_status(verified, "ga_readiness_manual_acceptance_report_required") == "failed"
    assert verified["status"] == "failed"


def test_ga_readiness_verifier_requires_external_final_handoff_binding(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    _fixture, _watch_store, _signoff_store, source, _queue_id = _final_fixture(tmp_path)
    final_store = TrustOperationsFinalReadinessStore(tmp_path / ".musicforge" / "trust-operations-final-readiness")
    final_store.refresh_report(source)
    final_store.create_certificate()
    final_store.sign({"signed_by": "ga-reviewer", "role": "owner", "reason": "Final handoff is ready for GA."})
    final_store.export_handoff(source)
    final_store.build_handoff_zip()
    final_store.verify_handoff_zip({"strict": True, "require_signed": True, "require_current": True, **source})
    ga_report = build_ga_readiness_report(
        repo_root=tmp_path,
        require_final_readiness=True,
        final_handoff_verification_report_path=final_store.verification_report_path(),
    )
    out = tmp_path / "ga-final.json"
    write_ga_readiness_report(ga_report, out)

    missing_external = verify_ga_readiness_report(out, require_final_readiness=True)
    with_external = verify_ga_readiness_report(
        out,
        require_final_readiness=True,
        final_handoff_package_path=final_store.handoff_zip_path(),
        final_handoff_verification_report_path=final_store.verification_report_path(),
    )

    assert _check_status(missing_external, "ga_readiness_final_handoff_package_required") == "failed"
    assert _check_status(with_external, "ga_readiness_final_handoff_zip_binding") == "passed"
    assert _check_status(with_external, "ga_readiness_final_handoff_ga_binding") == "passed"


def test_ga_readiness_verifier_requires_external_audio_campaign_remediation_binding(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_repo(tmp_path)
    server = start_test_server()
    try:
        release_id, campaign_id, remediation_store = _needs_fix_release_campaign(server, "GA Remediation Track")
        _complete_first_fix_sprint(server, campaign_id, remediation_store, release_id)
        remediation_store.closeout_report(release_id)
        remediation_store.signoff(release_id, {"signed_by": "QA", "role": "developer"})
        zipped = remediation_store.build_zip(release_id)
        verification = remediation_store.verify_zip(release_id, strict=True, require_passed=True, require_signed=True)
        ga_report = build_ga_readiness_report(
            repo_root=tmp_path,
            require_audio_campaign_remediation=True,
            audio_campaign_remediation_zip_path=zipped["zip_path"],
            audio_campaign_remediation_verification_report_path=remediation_store.verification_report_path(release_id),
        )
        out = tmp_path / "ga-remediation.json"
        write_ga_readiness_report(ga_report, out)
        missing_external = verify_ga_readiness_report(out, require_audio_campaign_remediation=True)
        with_external = verify_ga_readiness_report(
            out,
            require_audio_campaign_remediation=True,
            audio_campaign_remediation_path=zipped["zip_path"],
            audio_campaign_remediation_verification_report_path=remediation_store.verification_report_path(release_id),
        )
    finally:
        stop_test_server(server)

    assert verification["status"] == "passed"
    assert _check_status(missing_external, "ga_readiness_audio_campaign_remediation_package_required") == "failed"
    assert _check_status(with_external, "ga_readiness_audio_campaign_remediation_zip_binding") == "passed"
    assert _check_status(with_external, "ga_readiness_audio_campaign_remediation_ga_binding") == "passed"


def _check_status(report: dict, check_id: str) -> str:
    for check in report.get("checks", []):
        if check.get("check_id") == check_id:
            return str(check.get("status") or "")
    return ""
