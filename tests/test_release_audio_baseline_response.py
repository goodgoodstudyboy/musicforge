from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from song_agent.release_audio_baseline_governance import ReleaseAudioBaselineGovernanceStore
from song_agent.release_audio_baseline_governance_verifier import verify_release_audio_baseline_registry_package
from song_agent.release_audio_regression import ReleaseAudioRegressionStore
from song_agent.release_audio_regression_response import ReleaseAudioRegressionResponseStateError, ReleaseAudioRegressionResponseStore
from song_agent.release_audio_regression_response_verifier import verify_release_audio_regression_response_package
from song_agent.releases import stable_hash
from tests.test_release_audio_regression import _configure_regression, _prepare_signed_timeline
from tests.test_server_releases import start_test_server, stop_test_server


def _prepare_regression_pair(server, title: str = "Baseline Governance Track"):
    baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, title)
    current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, title)
    regression_store = ReleaseAudioRegressionStore(
        release_store=server.release_store,
        certification_store=current_store.certification_store,
        timeline_store=current_store,
    )
    _configure_regression(regression_store, current_release_id, baseline_release_id, baseline_timeline_id, baseline_store, current_timeline_id, current_store)
    return baseline_release_id, baseline_timeline_id, baseline_store, current_release_id, current_timeline_id, current_store, regression_store


def test_release_audio_baseline_governance_lifecycle_and_verifier(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store, *_ = _prepare_regression_pair(server)
        store = ReleaseAudioBaselineGovernanceStore(release_store=server.release_store)
        baseline = store.create_from_release(
            baseline_release_id,
            {
                "timeline": baseline_store.zip_path(baseline_release_id, baseline_timeline_id),
                "timeline_verification_report": baseline_store.verification_report_path(baseline_release_id, baseline_timeline_id),
                "certification": baseline_store.certification_store.zip_path(baseline_release_id),
                "certification_verification_report": baseline_store.certification_store.verification_report_path(baseline_release_id),
            },
        )
        approved = store.approve(baseline["baseline_id"], {"approved_by": "QA", "reason": "baseline approved"})
        active = store.activate(approved["baseline_id"])
        zipped = store.build_zip()
        verification = verify_release_audio_baseline_registry_package(zipped["zip_path"], strict=True, require_active=True)
    finally:
        stop_test_server(server)

    assert baseline["track_set"]["track_count"] >= 1
    assert active["status"] == "active"
    assert verification["status"] == "passed", verification.get("blockers")


def test_release_audio_baseline_registry_rejects_declared_extra(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store, *_ = _prepare_regression_pair(server, "Baseline Extra Track")
        store = ReleaseAudioBaselineGovernanceStore(release_store=server.release_store)
        baseline = store.create_from_release(
            baseline_release_id,
            {
                "timeline": baseline_store.zip_path(baseline_release_id, baseline_timeline_id),
                "timeline_verification_report": baseline_store.verification_report_path(baseline_release_id, baseline_timeline_id),
                "certification": baseline_store.certification_store.zip_path(baseline_release_id),
                "certification_verification_report": baseline_store.certification_store.verification_report_path(baseline_release_id),
            },
        )
        store.approve(baseline["baseline_id"], {"approved_by": "QA", "reason": "baseline approved"})
        store.activate(baseline["baseline_id"])
        store.build_zip()
        extra_path = store.export_dir() / "baselines" / baseline["baseline_id"] / "extra.txt"
        extra_path.write_text("unexpected", encoding="utf-8")
        manifest_path = store.export_dir() / "manifest.json"
        manifest = read_json(manifest_path)
        manifest["files"].append({"path": f"baselines/{baseline['baseline_id']}/extra.txt", "size_bytes": extra_path.stat().st_size, "sha256": "not-used"})
        manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
        write_json(manifest_path, manifest)
        import zipfile

        with zipfile.ZipFile(store.zip_path(), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(store.export_dir().rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(store.export_dir()).as_posix())
        verification = verify_release_audio_baseline_registry_package(store.zip_path(), strict=True, require_active=True)
    finally:
        stop_test_server(server)

    assert verification["status"] == "failed"
    assert "audio_baseline_registry_zip_allowed_entries" in verification["blockers"]


def test_release_audio_regression_response_lifecycle_and_signed_tamper_guard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        *_, current_release_id, _current_timeline_id, _current_store, regression_store = _prepare_regression_pair(server, "Response Lifecycle Track")
        regression_store.refresh_report(current_release_id)
        regression_store.signoff(current_release_id, {"signed_by": "QA", "role": "developer"})
        regression_store.build_zip(current_release_id)
        regression_store.verify_zip(current_release_id, strict=True, require_passed=True, require_signed=True, require_current=True, require_baseline_current=True)
        store = ReleaseAudioRegressionResponseStore(release_store=server.release_store, regression_store=regression_store)
        plan = store.create_plan(current_release_id)
        run = store.run_safe_actions(current_release_id)
        closeout = store.closeout(current_release_id, {"closed_by": "QA", "reason": "recheck passed"})
        signoff = store.signoff(current_release_id, {"signed_by": "QA", "role": "developer"})
        zipped = store.build_zip(current_release_id)
        verification = verify_release_audio_regression_response_package(
            zipped["zip_path"],
            strict=True,
            require_closed=True,
            require_signed=True,
            require_regression_current=True,
            **store._response_verifier_kwargs(current_release_id),  # noqa: SLF001 - test exercises store-resolved external evidence.
        )

        report = read_json(store.plan_path(current_release_id))
        report["summary"]["action_count"] = 99
        report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
        write_json(store.plan_path(current_release_id), report)
        export_error = None
        try:
            store.export_package(current_release_id)
        except ReleaseAudioRegressionResponseStateError as exc:
            export_error = str(exc)
    finally:
        stop_test_server(server)

    assert plan["status"] == "closed"
    assert run["status"] == "completed_with_manual_actions"
    assert closeout["status"] == "closed"
    assert signoff["signoff"]["status"] == "signed"
    assert verification["status"] == "passed", verification.get("blockers")
    assert export_error is not None
    assert "plan_hash" in export_error


def test_release_audio_regression_response_rejects_high_waiver(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, "Response High Baseline")
        current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, "Response High Current")
        regression_store = ReleaseAudioRegressionStore(release_store=server.release_store, certification_store=current_store.certification_store, timeline_store=current_store)
        _configure_regression(regression_store, current_release_id, baseline_release_id, baseline_timeline_id, baseline_store, current_timeline_id, current_store)
        report = regression_store.refresh_report(current_release_id)
        store = ReleaseAudioRegressionResponseStore(release_store=server.release_store, regression_store=regression_store)
        plan = store.create_plan(current_release_id)
        action_id = read_json(store.action_path(current_release_id))["actions"][0]["action_id"]
        waiver_error = None
        try:
            store.add_waiver(current_release_id, {"action_id": action_id, "reason": "waive high issue", "waived_by": "QA"})
        except ReleaseAudioRegressionResponseStateError as exc:
            waiver_error = str(exc)
    finally:
        stop_test_server(server)

    assert report["status"] == "failed"
    assert plan["status"] == "needs_response"
    assert waiver_error is not None
    assert "High and critical" in waiver_error
