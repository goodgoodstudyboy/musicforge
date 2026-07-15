from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from song_agent.audio_campaign_remediation import AudioCampaignRemediationStateError, AudioCampaignRemediationStore
from song_agent.audio_campaign_remediation_verifier import verify_audio_campaign_remediation_package
from song_agent.projectio import read_json, write_json
from song_agent.releases import stable_hash
from tests.test_release_audio_campaign_planner import _release_with_audio_track
from tests.test_server_releases import start_test_server, stop_test_server


def _needs_fix_release_campaign(server, title: str) -> tuple[str, str, AudioCampaignRemediationStore]:
    release_id, _project_id = _release_with_audio_track(server, title)
    created = server.audio_campaign_planner_store.create_campaign_from_release(release_id)
    campaign_id = created["campaign"]["campaign_id"]
    session_id = created["session"]["session_id"]
    item_id = created["session"]["items"][0]["item_id"]
    server.audio_lab_store.write_item_review(
        session_id,
        item_id,
        {"result": "needs_fix", "rating": 2, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True},
    )
    server.audio_lab_store.add_marker(session_id, item_id, {"time_seconds": 1.0, "category": "mix_balance", "severity": "high", "message": "Hook masked."})
    server.audio_campaign_store.refresh_report(campaign_id)
    store = AudioCampaignRemediationStore(
        release_store=server.release_store,
        project_store=server.project_store,
        planner_store=server.audio_campaign_planner_store,
        campaign_store=server.audio_campaign_store,
        fix_sprint_store=server.audio_campaign_store.audio_fix_sprint_store,
    )
    return release_id, campaign_id, store


def _complete_first_fix_sprint(server, campaign_id: str, store: AudioCampaignRemediationStore, release_id: str) -> str:
    store.run_safe_actions(release_id)
    campaign = server.audio_campaign_store.read_campaign(campaign_id)
    sprint_id = str(campaign["cases"][0]["fix"]["fix_sprint_id"])
    fix_store = server.audio_campaign_store.audio_fix_sprint_store
    sprint = fix_store.read_sprint(sprint_id)
    item_id = str(sprint["items"][0]["fix_item_id"])
    candidate_id = str(sprint["items"][0]["candidates"][0]["candidate_id"])
    fix_store.review_candidate(sprint_id, item_id, candidate_id, {"preferred": "right", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
    fix_store.select_candidate(sprint_id, item_id, candidate_id)
    store.run_safe_actions(release_id)
    recheck = fix_store._read_recheck_session(sprint_id)  # type: ignore[attr-defined]
    fix_store.review_recheck_item(sprint_id, str(recheck["items"][0]["item_id"]), {"result": "accepted", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
    store.run_safe_actions(release_id)
    return sprint_id


def test_audio_campaign_remediation_lifecycle_and_verifier(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, campaign_id, store = _needs_fix_release_campaign(server, "Remediation Store Track")
        plan = store.refresh_plan(release_id)
        first_run = store.run_safe_actions(release_id)
        before_manual = store.closeout_report(release_id)
        first_sprints = [row.get("fix", {}).get("fix_sprint_id") for row in server.audio_campaign_store.read_campaign(campaign_id).get("cases", [])]
        second_run = store.run_safe_actions(release_id)
        second_sprints = [row.get("fix", {}).get("fix_sprint_id") for row in server.audio_campaign_store.read_campaign(campaign_id).get("cases", [])]

        sprint_id = _complete_first_fix_sprint(server, campaign_id, store, release_id)
        closeout = store.closeout_report(release_id)
        signed = store.signoff(release_id, {"signed_by": "QA", "role": "developer"})
        zipped = store.build_zip(release_id)
        verification = verify_audio_campaign_remediation_package(zipped["zip_path"], strict=True, require_passed=True, require_signed=True)
    finally:
        stop_test_server(server)

    assert plan["status"] == "needs_action"
    assert first_run["queue"]["summary"]["manual_required_count"] > 0
    assert before_manual["status"] == "failed"
    assert "manual_action_required" in before_manual["blockers"]
    assert first_sprints == second_sprints
    assert second_run["closeout"]["status"] == "failed"
    assert sprint_id.startswith("afs-")
    assert closeout["status"] == "passed"
    assert signed["signoff"]["status"] == "signed"
    assert verification["status"] == "passed", verification["blockers"]
    assert verification["summary"]["zip_path"] == "audio-campaign-remediation.zip"


def test_audio_campaign_remediation_blocks_stale_final_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _campaign_id, store = _needs_fix_release_campaign(server, "Remediation Stale Track")
        track = server.release_store.get_release(release_id).tracks[0]
        manifest_path = server.project_store.project_dir(track.project_id) / "final-export" / "manifest.json"
        manifest = read_json(manifest_path)
        manifest["tampered_after_release_track"] = True
        write_json(manifest_path, manifest)
        plan = store.refresh_plan(release_id)
        with pytest.raises(AudioCampaignRemediationStateError):
            store.run_safe_actions(release_id)
    finally:
        stop_test_server(server)

    assert plan["status"] == "blocked"
    assert any(row["check_id"] == "release_track_final_export_current" for row in plan["blockers"])


def test_signed_audio_campaign_remediation_blocks_current_final_export_drift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, campaign_id, store = _needs_fix_release_campaign(server, "Remediation Signed Stale Track")
        _complete_first_fix_sprint(server, campaign_id, store, release_id)
        closeout = store.closeout_report(release_id)
        store.signoff(release_id, {"signed_by": "QA", "role": "developer"})
        track = server.release_store.get_release(release_id).tracks[0]
        manifest_path = server.project_store.project_dir(track.project_id) / "final-export" / "manifest.json"
        manifest = read_json(manifest_path)
        manifest["tampered_after_remediation_signoff"] = True
        write_json(manifest_path, manifest)

        gate = store.gate(release_id, required=True, require_signed=True)
        with pytest.raises(AudioCampaignRemediationStateError):
            store.export_package(release_id)
        with pytest.raises(AudioCampaignRemediationStateError):
            store.build_zip(release_id)
        with pytest.raises(AudioCampaignRemediationStateError):
            store.verify_zip(release_id, strict=True, require_passed=True, require_signed=True)
    finally:
        stop_test_server(server)

    assert closeout["status"] == "passed"
    assert gate["status"] == "failed"
    assert gate["hard_block"] is True
    assert "stale" in gate["message"].lower()


def test_audio_campaign_remediation_verifier_rejects_declared_extra_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, campaign_id, store = _needs_fix_release_campaign(server, "Remediation Extra File Track")
        _complete_first_fix_sprint(server, campaign_id, store, release_id)
        store.closeout_report(release_id)
        store.signoff(release_id, {"signed_by": "QA", "role": "developer"})
        zipped = store.build_zip(release_id)
        original_zip = Path(zipped["zip_path"])
        tampered_zip = tmp_path / "declared-extra-remediation.zip"
        _add_declared_extra_to_remediation_zip(original_zip, tampered_zip)
        verification = verify_audio_campaign_remediation_package(tampered_zip, strict=True, require_passed=True, require_signed=True)
    finally:
        stop_test_server(server)

    assert verification["status"] == "failed"
    assert "audio_campaign_remediation_zip_allowed_entries" in verification["blockers"]


def _add_declared_extra_to_remediation_zip(source_zip: Path, target_zip: Path) -> None:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = {info.filename: src.read(info.filename) for info in src.infolist()}
    extra_path = "extra.txt"
    extra_data = b"declared but not allowed\n"
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
