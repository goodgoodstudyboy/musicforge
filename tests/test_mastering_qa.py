from __future__ import annotations

import zipfile
from pathlib import Path

from song_agent.mastering_profiles import MasteringProfileStore
from song_agent.mastering_qa import MasteringStore, mastering_analysis_integrity_ok, mastering_candidate_integrity_ok
from song_agent.release_verifier import verify_release_zip
from tests.audio_fixtures import write_test_wav
from tests.test_release_audio import _add_final_export_audio, _signed_project
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_mastering_profile_analysis_plan_candidate_and_integrity(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Mastering Unit Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Mastering Unit Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})

        store = MasteringStore(server.release_store, project_store=server.project_store, profile_store=server.mastering_profile_store)
        profile = server.mastering_profile_store.get_profile("demo_review")
        analysis = store.analyze(release_id, {"profile_id": profile.profile_id})
        plan = store.build_plan(release_id, {})
        candidate = store.render_candidate(release_id, {})
        reviewed = store.review_candidate(release_id, candidate["candidate_id"], {"status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "Manual mastering A/B accepted."})
        selected = store.select_candidate(release_id, candidate["candidate_id"])
        gate = store.gate(release_id, required=True)
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert analysis["status"] in {"passed", "warning"}
    assert mastering_analysis_integrity_ok(analysis)
    assert plan["summary"]["track_count"] == 1
    assert candidate["status"] == "ready_for_review"
    assert reviewed["review"]["status"] == "accepted"
    assert selected["selected"] is True
    assert mastering_candidate_integrity_ok(selected)
    assert gate["status"] == "passed"


def test_mastering_release_api_export_signoff_verifier_and_signed_guard(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        first_project = _signed_project(server, "Mastering API One")
        second_project = _signed_project(server, "Mastering API Two")
        _add_final_export_audio(server, first_project, duration_seconds=30)
        _add_final_export_audio(server, second_project, duration_seconds=30)
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Mastering API Release", "release_type": "ep", "primary_artist": "MusicForge"})
        release_id = release["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first_project})
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": second_project})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        analyze_status, analyze = request_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
        plan_status, plan = request_json(server, "POST", f"/api/releases/{release_id}/mastering/plan", {})
        candidate_status, candidate = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/mastering/candidates",
            {},
            timeout=180,
        )
        candidate_id = candidate["candidate"]["candidate_id"]
        review_status, _review = request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "Manual A/B accepted."})
        select_status, selected = request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/select", {})
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_mastering_qa": True})
        signed_mutation_status, signed_mutation = request_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
        zip_path = Path(".musicforge") / "releases" / release_id / "release-export.zip"
        verify = verify_release_zip(zip_path, require_audio=True, require_mastering=True)
        with zipfile.ZipFile(zip_path) as archive:
            track_wav = next(name for name in archive.namelist() if name.startswith("tracks/") and name.endswith("/song.wav"))

        tampered_zip = _rewrite_zip(zip_path, tmp_path / "tampered-mastering.zip", {track_wav: lambda data: b"not-a-real-wav"})
        tampered = verify_release_zip(tampered_zip, require_audio=True, require_mastering=True)
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert analyze_status == 200
    assert analyze["summary"]["status"] in {"passed", "warning"}
    assert plan_status == 200
    assert plan["plan"]["summary"]["track_count"] == 2
    assert candidate_status == 201
    assert review_status == 200
    assert select_status == 200
    assert selected["candidate"]["selected"] is True
    assert export_status == 200
    assert export["manifest"]["mastering"]["status"] in {"passed", "warning"}
    assert zip_status == 200
    assert sign_status == 200
    assert signoff["signoff"]["acceptance_gate"]["mastering"]["status"] == "passed"
    assert signed_mutation_status == 409
    assert "Signed releases" in signed_mutation["error"]
    assert verify["status"] in {"passed", "warning"}
    assert _check(verify, "mastering_evidence")["status"] == "passed"
    assert tampered["status"] == "failed"
    assert _check(tampered, "mastering_evidence")["status"] == "failed"


def test_mastering_signoff_blocks_stale_candidate_after_track_audio_changes(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Mastering Stale Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Mastering Stale Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/plan", {})
        candidate_status, candidate = request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates", {})
        candidate_id = candidate["candidate"]["candidate_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/select", {})

        project_dir = Path(".musicforge") / "projects" / project_id
        write_test_wav(project_dir / "final-export" / "song.wav", duration_seconds=30, amplitude=0.1)
        stale_status, stale = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_mastering_qa": True})
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert candidate_status == 201
    assert stale_status == 409
    assert "stale" in stale["error"].lower()


def test_mastering_signoff_requires_selected_candidate_after_analysis(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Mastering Analysis Only Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Mastering Analysis Only Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        analyze_status, analyze = request_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
        export_status, _export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_mastering_qa": True})
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert analyze_status == 200
    assert analyze["summary"]["status"] in {"passed", "warning"}
    assert export_status == 200
    assert zip_status == 200
    assert sign_status == 409
    assert "selected mastered candidate" in signoff["error"].lower()


def test_mastering_signoff_blocks_export_built_before_mastering_selection(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Mastering Stale Export Track")
        _add_final_export_audio(server, project_id, duration_seconds=30)
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Mastering Stale Export Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        early_export_status, early_export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        early_zip_status, _early_zip = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/plan", {})
        candidate_status, candidate = request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates", {})
        candidate_id = candidate["candidate"]["candidate_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True})
        request_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/select", {})
        stale_sign_status, stale_sign = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_mastering_qa": True})
        rebuilt_export_status, rebuilt_export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        rebuilt_zip_status, _rebuilt_zip = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_mastering_qa": True})
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert early_export_status == 200
    assert early_export["manifest"]["mastering"]["selected_candidate_id"] is None
    assert early_zip_status == 200
    assert candidate_status == 201
    assert stale_sign_status == 409
    assert "release export is stale" in stale_sign["error"].lower()
    assert stale_sign["acceptance_gate"]["mastering_export"]["status"] == "failed"
    assert rebuilt_export_status == 200
    assert rebuilt_export["manifest"]["mastering"]["selected_candidate_id"] == candidate_id
    assert rebuilt_zip_status == 200
    assert sign_status == 200
    assert signoff["signoff"]["acceptance_gate"]["mastering"]["status"] == "passed"


def test_mastering_profile_crud_blocks_builtin_update(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = MasteringProfileStore(Path(".musicforge") / "mastering-profiles")
    profiles = store.list_profiles()
    assert any(profile.profile_id == "streaming_balanced" for profile in profiles)
    clone = store.clone_profile("streaming_balanced", {"profile_id": "mprof-test", "name": "Test Mastering"})
    updated = store.update_profile(clone.profile_id, {"target_loudness_proxy_db": -16.0})
    assert updated.target_loudness_proxy_db == -16.0
    try:
        store.update_profile("streaming_balanced", {"name": "mutate"})
    except Exception as exc:
        assert "read-only" in str(exc)
    else:
        raise AssertionError("Built-in profile update should fail.")


def _rewrite_zip(source: Path, target: Path, transforms: dict[str, object]) -> Path:
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            transform = transforms.get(info.filename)
            if transform is not None:
                data = transform(data)
            dst.writestr(info.filename, data)
    return target


def _check(report: dict, check_id: str) -> dict:
    for item in [*report.get("checks", []), *report.get("track_checks", [])]:
        if item.get("check_id") == check_id:
            return item
    raise AssertionError(check_id)
