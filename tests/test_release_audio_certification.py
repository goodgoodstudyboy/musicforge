from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from song_agent.ga_readiness import build_ga_readiness_report, write_ga_readiness_report
from song_agent.ga_readiness_verifier import verify_ga_readiness_report
from song_agent.projectio import read_json, write_json
from song_agent.release_audio_certification import ReleaseAudioCertificationStateError, ReleaseAudioCertificationStore
from song_agent.release_audio_certification_verifier import verify_release_audio_certification_package
from song_agent.releases import stable_hash
from tests.test_release_audio_campaign_planner import _release_with_audio_track
from tests.test_server_releases import start_test_server, stop_test_server


def _prepare_certified_release(server, title: str = "Certified Release Track") -> tuple[str, str, ReleaseAudioCertificationStore]:
    release_id, _project_id = _release_with_audio_track(server, title)
    created = server.audio_campaign_planner_store.create_campaign_from_release(release_id)
    campaign_id = created["campaign"]["campaign_id"]
    session_id = created["session"]["session_id"]
    item_id = created["session"]["items"][0]["item_id"]
    server.audio_lab_store.write_item_review(
        session_id,
        item_id,
        {"result": "accepted", "rating": 5, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True},
    )
    server.audio_campaign_store.refresh_report(campaign_id)
    server.audio_campaign_store.signoff(campaign_id, {"signed_by": "QA", "role": "developer"})
    server.audio_campaign_governance_store.build_archive_zip(campaign_id)
    governance = server.audio_campaign_governance_store.verify_archive(campaign_id, {"strict": True})
    assert governance["status"] == "passed", governance.get("blockers")
    store = ReleaseAudioCertificationStore(
        release_store=server.release_store,
        project_store=server.project_store,
        planner_store=server.audio_campaign_planner_store,
        campaign_store=server.audio_campaign_store,
        governance_store=server.audio_campaign_governance_store,
        remediation_store=server.audio_campaign_remediation_store,
    )
    return release_id, campaign_id, store


def test_release_audio_certification_lifecycle_ga_and_verifier(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, campaign_id, store = _prepare_certified_release(server)
        report = store.refresh_report(release_id)
        signoff = store.signoff(release_id, {"signed_by": "QA", "role": "developer"})
        zipped = store.build_zip(release_id)
        verification = store.verify_zip(
            release_id,
            strict=True,
            require_passed=True,
            require_signed=True,
            require_real_audio=True,
            require_manual_review=True,
            require_remediation_when_needed=True,
        )
        repo_root = Path(__file__).resolve().parents[1]
        ga_report = build_ga_readiness_report(
            repo_root=repo_root,
            allow_dirty=True,
            require_release_audio_certification=True,
            release_audio_certification_zip_path=zipped["zip_path"],
            release_audio_certification_verification_report_path=store.verification_report_path(release_id),
        )
        ga_report_path = tmp_path / "ga-readiness.json"
        write_ga_readiness_report(ga_report, ga_report_path)
        ga_verification = verify_ga_readiness_report(
            ga_report_path,
            require_release_audio_certification=True,
            release_audio_certification_path=zipped["zip_path"],
            release_audio_certification_verification_report_path=store.verification_report_path(release_id),
        )
    finally:
        stop_test_server(server)

    assert report["status"] == "passed"
    assert report["campaign_id"] == campaign_id
    assert signoff["signoff"]["status"] == "signed"
    assert verification["status"] == "passed", verification.get("blockers")
    assert verification["summary"]["zip_path"] == "release-audio-certification.zip"
    assert ga_report["summary"]["release_audio_certification_status"] == "passed"
    assert ga_verification["status"] != "failed", ga_verification.get("blockers")
    assert _verification_check_status(ga_verification, "ga_readiness_release_audio_certification_ga_binding") == "passed"


def test_signed_release_audio_certification_blocks_current_final_export_drift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _campaign_id, store = _prepare_certified_release(server, "Certification Stale Export Track")
        store.signoff(release_id, {"signed_by": "QA", "role": "developer"})
        track = server.release_store.get_release(release_id).tracks[0]
        manifest_path = server.project_store.project_dir(track.project_id) / "final-export" / "manifest.json"
        manifest = read_json(manifest_path)
        manifest["tampered_after_certification_signoff"] = True
        write_json(manifest_path, manifest)

        gate = store.gate(release_id, required=True, require_signed=True)
        with pytest.raises(ReleaseAudioCertificationStateError):
            store.export_package(release_id)
        with pytest.raises(ReleaseAudioCertificationStateError):
            store.build_zip(release_id)
        with pytest.raises(ReleaseAudioCertificationStateError):
            store.verify_zip(release_id, strict=True, require_passed=True, require_signed=True)
    finally:
        stop_test_server(server)

    assert gate["status"] == "failed"
    assert gate["hard_block"] is True
    assert "stale" in gate["message"].lower()


def test_release_audio_certification_verifier_rejects_declared_extra_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _campaign_id, store = _prepare_certified_release(server, "Certification Extra File Track")
        store.signoff(release_id, {"signed_by": "QA", "role": "developer"})
        zipped = store.build_zip(release_id)
        tampered_zip = tmp_path / "declared-extra-certification.zip"
        _add_declared_extra_to_certification_zip(Path(zipped["zip_path"]), tampered_zip)
        verification = verify_release_audio_certification_package(tampered_zip, strict=True, require_passed=True, require_signed=True)
    finally:
        stop_test_server(server)

    assert verification["status"] == "failed"
    assert "release_audio_certification_zip_allowed_entries" in verification["blockers"]


def _add_declared_extra_to_certification_zip(source_zip: Path, target_zip: Path) -> None:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = {info.filename: src.read(info.filename) for info in src.infolist()}
    extra_path = "extra.txt"
    extra_data = b"declared but not allowed in release audio certification package\n"
    docs[extra_path] = extra_data
    manifest = json.loads(docs["manifest.json"].decode("utf-8"))
    manifest.setdefault("files", []).append({"path": extra_path, "size_bytes": len(extra_data), "sha256": hashlib.sha256(extra_data).hexdigest()})
    manifest["files"] = sorted(manifest["files"], key=lambda row: str(row.get("path") or ""))
    manifest.setdefault("zip", {})["entries"] = sorted(set(manifest.get("zip", {}).get("entries") or []) | {extra_path})
    manifest.setdefault("zip", {})["entry_count"] = len(manifest["zip"]["entries"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    docs["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name, data in docs.items():
            dst.writestr(name, data)


def _verification_check_status(report: dict, check_id: str) -> str:
    for check in report.get("checks") or []:
        if isinstance(check, dict) and check.get("check_id") == check_id:
            return str(check.get("status") or "")
    return ""
