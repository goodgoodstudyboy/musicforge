from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.audio_campaign_verifier import verify_audio_campaign_package
from song_agent.audio_campaigns import AudioCampaignStateError, AudioCampaignStore
from song_agent.audio_fix_sprints import AudioFixSprintStore
from song_agent.audio_lab import AudioLabStore, write_lab_test_wav
from song_agent.projectio import read_json, write_json
from song_agent.releases import stable_hash


def _session(lab: AudioLabStore, *, result: str = "accepted", release_ready: bool = True, marker: bool = False) -> str:
    smoke = lab.run_smoke({"cases": 1, "render_audio": "auto"})
    session = lab.create_session({"from_smoke": smoke["smoke_run_id"]})
    session_id = session["session_id"]
    item_id = session["items"][0]["item_id"]
    if release_ready:
        raw = read_json(lab.session_path(session_id))
        raw["items"][0]["renderer"] = {"runner_kind": "real", "profile_id": "test-real", "release_ready": True}
        raw["items"][0]["source_hash"] = f"release-ready-{session_id}"
        lab._write_session(raw)  # type: ignore[attr-defined]
    lab.write_item_review(
        session_id,
        item_id,
        {"result": result, "rating": 5 if result == "accepted" else 2, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True},
    )
    if marker:
        lab.add_marker(session_id, item_id, {"time_seconds": 1.0, "category": "mix_balance", "severity": "high", "message": "Hook is masked."})
    return session_id


def _close_real_fix_sprint(fix_store: AudioFixSprintStore, sprint_id: str) -> None:
    sprint = fix_store.read_sprint(sprint_id)
    item_id = sprint["items"][0]["fix_item_id"]
    candidate = fix_store.generate_candidates(sprint_id)["candidates"][0]
    fix_store.review_candidate(sprint_id, item_id, candidate["candidate_id"], {"preferred": "right", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
    fix_store.select_candidate(sprint_id, item_id, candidate["candidate_id"])
    recheck = fix_store.create_recheck_session(sprint_id)["recheck_session"]
    fix_store.review_recheck_item(sprint_id, recheck["items"][0]["item_id"], {"result": "accepted", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True})
    fix_store.close_sprint(sprint_id, {"closed_by": "QA"})


def test_audio_campaign_blocks_test_fake_audio_and_signs_real_campaign(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    fake_session = _session(lab, release_ready=False)
    store = AudioCampaignStore(audio_lab_store=lab, audio_fix_sprint_store=AudioFixSprintStore(audio_lab_store=lab))

    fake_campaign = store.create_campaign({"from_session": fake_session})
    fake_report = store.refresh_report(fake_campaign["campaign_id"])

    assert fake_report["status"] == "failed"
    assert "test_fake_audio_not_release_ready" in {row["check_id"] for row in fake_report["blockers"]}
    with pytest.raises(AudioCampaignStateError):
        store.signoff(fake_campaign["campaign_id"], {"signed_by": "QA"})

    real_session = _session(lab, release_ready=True)
    real_campaign = store.create_campaign({"from_session": real_session})
    report = store.refresh_report(real_campaign["campaign_id"])
    signoff = store.signoff(real_campaign["campaign_id"], {"signed_by": "QA", "role": "developer"})["signoff"]
    zip_result = store.build_zip(real_campaign["campaign_id"])
    verification = verify_audio_campaign_package(zip_result["zip_path"], require_real_audio=True, require_manual_review=True, require_signed=True)

    assert report["status"] == "passed"
    assert signoff["status"] == "signed"
    assert verification["status"] == "passed", verification["blockers"]


def test_audio_campaign_requires_fix_sprint_then_allows_closed_recheck(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    session_id = _session(lab, result="needs_fix", release_ready=True, marker=True)
    fix_store = AudioFixSprintStore(audio_lab_store=lab)
    store = AudioCampaignStore(audio_lab_store=lab, audio_fix_sprint_store=fix_store)

    campaign = store.create_campaign({"from_session": session_id})
    before = store.refresh_report(campaign["campaign_id"])
    created = store.create_fix_sprints(campaign["campaign_id"])
    sprint_id = created["fix_sprints"][0]["fix_sprint_id"]
    mid = store.refresh_report(campaign["campaign_id"])
    _close_real_fix_sprint(fix_store, sprint_id)
    after = store.refresh_report(campaign["campaign_id"])

    assert before["status"] == "failed"
    assert "fix_sprint_missing" in {row["check_id"] for row in before["blockers"]}
    assert mid["status"] == "failed"
    assert "fix_sprint_not_closed" in {row["check_id"] for row in mid["blockers"]}
    assert after["status"] == "passed", after["blockers"]
    assert after["summary"]["open_high_marker_count"] == 0


def test_audio_campaign_verifier_rejects_tamper_and_redaction(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    session_id = _session(lab, release_ready=True)
    store = AudioCampaignStore(audio_lab_store=lab, audio_fix_sprint_store=AudioFixSprintStore(audio_lab_store=lab))
    campaign = store.create_campaign({"from_session": session_id})
    store.signoff(campaign["campaign_id"], {"signed_by": "QA"})
    zip_result = store.build_zip(campaign["campaign_id"])
    zip_path = Path(zip_result["zip_path"])

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(zip_path) as src, zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "campaign-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["status"] = "failed"
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
    tamper_report = verify_audio_campaign_package(tampered, require_real_audio=True, require_manual_review=True, require_signed=True)

    redacted = tmp_path / "redacted.zip"
    with zipfile.ZipFile(zip_path) as src, zipfile.ZipFile(redacted, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "README.md":
                data += b"\nsk-secret-value C:\\Users\\demo\\secret.wav\n"
            dst.writestr(info.filename, data)
    redaction_report = verify_audio_campaign_package(redacted)

    assert tamper_report["status"] == "failed"
    assert "audio_campaign_report_integrity" in tamper_report["blockers"]
    assert redaction_report["status"] == "failed"
    assert "audio_campaign_redaction_scan" in redaction_report["blockers"]


def test_audio_campaign_sanitizes_manual_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    session_id = _session(lab, release_ready=True)
    store = AudioCampaignStore(audio_lab_store=lab, audio_fix_sprint_store=AudioFixSprintStore(audio_lab_store=lab))
    secret = r"sk-secret-value api_key=secret-value C:\Users\demo\secret.wav"

    campaign = store.create_campaign({"from_session": session_id, "name": f"Campaign {secret}"})
    store.signoff(campaign["campaign_id"], {"signed_by": f"Signer {secret}", "reason": f"Reason {secret}"})

    raw = read_json(store.campaign_path(campaign["campaign_id"]))
    signoff = read_json(store.signoff_path(campaign["campaign_id"]))
    serialized = str({"campaign": raw, "signoff": signoff})
    assert "sk-secret-value" not in serialized
    assert "api_key=secret-value" not in serialized
    assert r"C:\Users\demo\secret.wav" not in serialized
    assert "sk-[REDACTED]" in serialized
    assert "[REDACTED]" in serialized
    assert "[REDACTED_LOCAL_PATH]" in serialized
