from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from song_agent.ga_readiness import build_ga_readiness_report, write_ga_readiness_report
from song_agent.ga_readiness_verifier import verify_ga_readiness_report
from song_agent.projectio import read_json
from song_agent.release_audio_regression import ReleaseAudioRegressionStateError, ReleaseAudioRegressionStore
from song_agent.release_audio_regression_verifier import verify_release_audio_regression_package
from song_agent.releases import stable_hash
from tests.test_release_audio_timeline import _append_unexpected_file_to_zip, _prepare_timeline_release, _verification_check_status
from tests.test_server_releases import start_test_server, stop_test_server


def _prepare_signed_timeline(server, title: str) -> tuple[str, str, object]:
    release_id, _campaign_id, store = _prepare_timeline_release(server, title)
    refreshed = store.refresh_timeline(release_id)
    timeline_id = refreshed["timeline_id"]
    store.signoff_timeline(release_id, timeline_id, {"signed_by": "QA", "role": "developer"})
    store.build_zip(release_id, timeline_id)
    verification = store.verify_zip(
        release_id,
        timeline_id,
        strict=True,
        require_passed=True,
        require_signed=True,
        require_real_audio=True,
        require_manual_review=True,
        require_current_certification=True,
    )
    assert verification["status"] == "passed", verification.get("blockers")
    return release_id, timeline_id, store


def _configure_regression(store: ReleaseAudioRegressionStore, current_release_id: str, baseline_release_id: str, baseline_timeline_id: str, baseline_store, current_timeline_id: str, current_store) -> dict:
    return store.configure_baseline(
        current_release_id,
        {
            "baseline_release_id": baseline_release_id,
            "baseline_timeline": baseline_store.zip_path(baseline_release_id, baseline_timeline_id),
            "baseline_timeline_verification_report": baseline_store.verification_report_path(baseline_release_id, baseline_timeline_id),
            "baseline_certification": baseline_store.certification_store.zip_path(baseline_release_id),
            "baseline_certification_verification_report": baseline_store.certification_store.verification_report_path(baseline_release_id),
            "current_timeline": current_store.zip_path(current_release_id, current_timeline_id),
            "current_timeline_verification_report": current_store.verification_report_path(current_release_id, current_timeline_id),
            "current_certification": current_store.certification_store.zip_path(current_release_id),
            "current_certification_verification_report": current_store.certification_store.verification_report_path(current_release_id),
        },
    )


def _external_args(baseline_release_id: str, baseline_timeline_id: str, baseline_store, current_release_id: str, current_timeline_id: str, current_store) -> dict:
    return {
        "baseline_timeline_path": baseline_store.zip_path(baseline_release_id, baseline_timeline_id),
        "baseline_timeline_verification_report_path": baseline_store.verification_report_path(baseline_release_id, baseline_timeline_id),
        "baseline_certification_path": baseline_store.certification_store.zip_path(baseline_release_id),
        "baseline_certification_verification_report_path": baseline_store.certification_store.verification_report_path(baseline_release_id),
        "current_timeline_path": current_store.zip_path(current_release_id, current_timeline_id),
        "current_timeline_verification_report_path": current_store.verification_report_path(current_release_id, current_timeline_id),
        "current_certification_path": current_store.certification_store.zip_path(current_release_id),
        "current_certification_verification_report_path": current_store.certification_store.verification_report_path(current_release_id),
    }


def test_release_audio_regression_lifecycle_ga_and_verifier(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, "Regression Guard Track")
        current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, "Regression Guard Track")
        store = ReleaseAudioRegressionStore(release_store=server.release_store, certification_store=current_store.certification_store, timeline_store=current_store)
        _configure_regression(store, current_release_id, baseline_release_id, baseline_timeline_id, baseline_store, current_timeline_id, current_store)

        report = store.refresh_report(current_release_id)
        signoff = store.signoff(current_release_id, {"signed_by": "QA", "role": "developer"})
        zipped = store.build_zip(current_release_id)
        verification = store.verify_zip(current_release_id, strict=True, require_passed=True, require_signed=True, require_current=True, require_baseline_current=True)
        repo_root = Path(__file__).resolve().parents[1]
        ga_report = build_ga_readiness_report(
            repo_root=repo_root,
            allow_dirty=True,
            require_release_audio_regression_guard=True,
            release_audio_regression_zip_path=zipped["zip_path"],
            release_audio_regression_verification_report_path=store.verification_report_path(current_release_id),
            **_ga_external_args(baseline_release_id, baseline_timeline_id, baseline_store, current_release_id, current_timeline_id, current_store),
        )
        ga_path = tmp_path / "ga-regression.json"
        write_ga_readiness_report(ga_report, ga_path)
        ga_verification = verify_ga_readiness_report(
            ga_path,
            require_release_audio_regression_guard=True,
            release_audio_regression_path=zipped["zip_path"],
            release_audio_regression_verification_report_path=store.verification_report_path(current_release_id),
            **_ga_external_args(baseline_release_id, baseline_timeline_id, baseline_store, current_release_id, current_timeline_id, current_store),
        )
    finally:
        stop_test_server(server)

    assert report["status"] == "passed", report.get("blockers")
    assert signoff["signoff"]["status"] == "signed"
    assert verification["status"] == "passed", verification.get("blockers")
    assert ga_report["summary"]["release_audio_regression_guard_status"] == "passed"
    assert ga_verification["status"] != "failed", ga_verification.get("blockers")
    assert _verification_check_status(ga_verification, "ga_readiness_release_audio_regression_ga_binding") == "passed"


def test_release_audio_regression_rejects_tampered_current_certification_zip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, "Regression Tamper Track")
        current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, "Regression Tamper Track")
        store = ReleaseAudioRegressionStore(release_store=server.release_store, certification_store=current_store.certification_store, timeline_store=current_store)
        _configure_regression(store, current_release_id, baseline_release_id, baseline_timeline_id, baseline_store, current_timeline_id, current_store)
        store.signoff(current_release_id, {"signed_by": "QA", "role": "developer"})
        zipped = store.build_zip(current_release_id)
        _append_unexpected_file_to_zip(current_store.certification_store.zip_path(current_release_id))
        verification = verify_release_audio_regression_package(
            zipped["zip_path"],
            strict=True,
            require_passed=True,
            require_signed=True,
            require_current=True,
            require_baseline_current=True,
            **_external_args(baseline_release_id, baseline_timeline_id, baseline_store, current_release_id, current_timeline_id, current_store),
        )
        gate = store.gate(current_release_id, required=True, require_signed=True)
    finally:
        stop_test_server(server)

    assert verification["status"] == "failed"
    assert "release_audio_regression_current_certification_current" in verification["blockers"]
    assert gate["status"] == "failed"
    assert gate["hard_block"] is True


def test_release_audio_regression_verifier_rejects_internal_full_resign(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, "Regression Full Resign Baseline")
        current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, "Regression Full Resign Current")
        store = ReleaseAudioRegressionStore(release_store=server.release_store, certification_store=current_store.certification_store, timeline_store=current_store)
        _configure_regression(store, current_release_id, baseline_release_id, baseline_timeline_id, baseline_store, current_timeline_id, current_store)
        report = store.refresh_report(current_release_id)
        zipped = store.build_zip(current_release_id)
        tampered_zip = tmp_path / "regression-full-resign.zip"
        _rewrite_regression_as_passed(Path(zipped["zip_path"]), tampered_zip)
        verification = verify_release_audio_regression_package(
            tampered_zip,
            strict=True,
            require_passed=True,
            require_current=True,
            require_baseline_current=True,
            **_external_args(baseline_release_id, baseline_timeline_id, baseline_store, current_release_id, current_timeline_id, current_store),
        )
    finally:
        stop_test_server(server)

    assert report["status"] == "failed"
    assert verification["status"] == "failed"
    assert "release_audio_regression_track_matrix_binding" in verification["blockers"] or "release_audio_regression_internal_full_resign_guard" in verification["blockers"]


def test_release_audio_regression_history_blocks_deleted_signoff_refresh(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, "Regression Deleted Signoff Track")
        current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, "Regression Deleted Signoff Track")
        store = ReleaseAudioRegressionStore(release_store=server.release_store, certification_store=current_store.certification_store, timeline_store=current_store)
        _configure_regression(store, current_release_id, baseline_release_id, baseline_timeline_id, baseline_store, current_timeline_id, current_store)
        store.signoff(current_release_id, {"signed_by": "QA", "role": "developer"})
        store.signoff_path(current_release_id).unlink()
        refresh_error = None
        try:
            store.refresh_report(current_release_id)
        except ReleaseAudioRegressionStateError as exc:
            refresh_error = str(exc)
    finally:
        stop_test_server(server)

    assert refresh_error is not None
    assert "signed" in refresh_error.lower()


def test_release_audio_regression_signed_export_rejects_tampered_documents(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store = _prepare_signed_timeline(server, "Regression Signed Tamper Track")
        current_release_id, current_timeline_id, current_store = _prepare_signed_timeline(server, "Regression Signed Tamper Track")
        store = ReleaseAudioRegressionStore(release_store=server.release_store, certification_store=current_store.certification_store, timeline_store=current_store)
        _configure_regression(store, current_release_id, baseline_release_id, baseline_timeline_id, baseline_store, current_timeline_id, current_store)
        store.signoff(current_release_id, {"signed_by": "QA", "role": "developer"})

        report = read_json(store.report_path(current_release_id))
        report["summary"]["blocker_count"] = 99
        report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
        store.report_path(current_release_id).write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        report_export_error = None
        try:
            store.export_package(current_release_id)
        except ReleaseAudioRegressionStateError as exc:
            report_export_error = str(exc)

        docs = store._build_documents(current_release_id)  # noqa: SLF001 - regression setup needs exact signed fixture restore.
        store._write_documents(current_release_id, docs)  # noqa: SLF001

        matrix = read_json(store.matrix_path(current_release_id))
        matrix["summary"]["failed_track_count"] = 7
        matrix["integrity_hash"] = stable_hash({key: value for key, value in matrix.items() if key != "integrity_hash"})
        store.matrix_path(current_release_id).write_text(json.dumps(matrix, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        matrix_zip_error = None
        try:
            store.build_zip(current_release_id)
        except ReleaseAudioRegressionStateError as exc:
            matrix_zip_error = str(exc)
    finally:
        stop_test_server(server)

    assert report_export_error is not None
    assert "regression_report_hash" in report_export_error
    assert matrix_zip_error is not None
    assert "track_matrix_hash" in matrix_zip_error


def _ga_external_args(baseline_release_id: str, baseline_timeline_id: str, baseline_store, current_release_id: str, current_timeline_id: str, current_store) -> dict:
    return {
        "release_audio_regression_baseline_timeline_path": baseline_store.zip_path(baseline_release_id, baseline_timeline_id),
        "release_audio_regression_baseline_timeline_verification_report_path": baseline_store.verification_report_path(baseline_release_id, baseline_timeline_id),
        "release_audio_regression_baseline_certification_path": baseline_store.certification_store.zip_path(baseline_release_id),
        "release_audio_regression_baseline_certification_verification_report_path": baseline_store.certification_store.verification_report_path(baseline_release_id),
        "release_audio_regression_current_timeline_path": current_store.zip_path(current_release_id, current_timeline_id),
        "release_audio_regression_current_timeline_verification_report_path": current_store.verification_report_path(current_release_id, current_timeline_id),
        "release_audio_regression_current_certification_path": current_store.certification_store.zip_path(current_release_id),
        "release_audio_regression_current_certification_verification_report_path": current_store.certification_store.verification_report_path(current_release_id),
    }


def _rewrite_regression_as_passed(source_zip: Path, target_zip: Path) -> None:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = {info.filename: src.read(info.filename) for info in src.infolist()}
    report = json.loads(docs["regression-report.json"].decode("utf-8"))
    matrix = json.loads(docs["track-regression-matrix.json"].decode("utf-8"))
    issues = json.loads(docs["issue-regression-index.json"].decode("utf-8"))
    quality = json.loads(docs["quality-delta-summary.json"].decode("utf-8"))
    blockers = json.loads(docs["blocker-register.json"].decode("utf-8"))
    report["status"] = "passed"
    report["readiness"] = "ready"
    report["blockers"] = []
    report["warnings"] = []
    report["summary"]["blocker_count"] = 0
    report["summary"]["failed_track_count"] = 0
    for row in matrix.get("rows") or []:
        row["status"] = "passed"
        row["blockers"] = []
        row["identity_status"] = "matched"
    matrix["summary"]["failed_track_count"] = 0
    matrix["summary"]["passed_track_count"] = len(matrix.get("rows") or [])
    issues["new_issues"] = []
    issues["issue_taxonomy"] = []
    quality["decision"] = {"status": "passed", "recommendation": "audio_regression_guard_passed", "blockers": [], "warnings": []}
    blockers["status"] = "passed"
    blockers["summary"] = {"blocker_count": 0, "warning_count": 0}
    blockers["blockers"] = []
    blockers["warnings"] = []
    for doc in (matrix, issues, quality, blockers):
        doc["integrity_hash"] = stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})
    report["source"]["track_matrix_hash"] = matrix["integrity_hash"]
    report["source"]["issue_index_hash"] = issues["integrity_hash"]
    report["source"]["quality_delta_hash"] = quality["integrity_hash"]
    report["source"]["blocker_register_hash"] = blockers["integrity_hash"]
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    manifest = json.loads(docs["manifest.json"].decode("utf-8"))
    manifest["report_hash"] = report["integrity_hash"]
    manifest["track_matrix_hash"] = matrix["integrity_hash"]
    manifest["issue_index_hash"] = issues["integrity_hash"]
    manifest["quality_delta_hash"] = quality["integrity_hash"]
    manifest["blocker_register_hash"] = blockers["integrity_hash"]
    docs["regression-report.json"] = _json_bytes(report)
    docs["track-regression-matrix.json"] = _json_bytes(matrix)
    docs["issue-regression-index.json"] = _json_bytes(issues)
    docs["quality-delta-summary.json"] = _json_bytes(quality)
    docs["blocker-register.json"] = _json_bytes(blockers)
    files = []
    for name, data in sorted(docs.items()):
        if name == "manifest.json":
            continue
        files.append({"path": name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest["files"] = files
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    docs["manifest.json"] = _json_bytes(manifest)
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name, data in docs.items():
            dst.writestr(name, data)


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
