from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.audio_campaign_archive_verifier import verify_audio_campaign_archive_package
from song_agent.audio_campaign_governance import AudioCampaignGovernanceStateError, AudioCampaignGovernanceStore
from song_agent.audio_campaigns import AudioCampaignStore
from song_agent.audio_fix_sprints import AudioFixSprintStore
from song_agent.audio_lab import AudioLabStore, write_lab_test_wav
from song_agent.ga_readiness import build_ga_readiness_report, write_ga_readiness_report
from song_agent.ga_readiness_verifier import verify_ga_readiness_report
from song_agent.projectio import read_json
from song_agent.releases import stable_hash


def _signed_campaign(tmp_path: Path, monkeypatch) -> tuple[AudioCampaignStore, AudioCampaignGovernanceStore, str]:
    monkeypatch.chdir(tmp_path)
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    smoke = lab.run_smoke({"cases": 1, "render_audio": "auto"})
    session = lab.create_session({"from_smoke": smoke["smoke_run_id"]})
    session_id = session["session_id"]
    raw = read_json(lab.session_path(session_id))
    raw["items"][0]["renderer"] = {"runner_kind": "real", "profile_id": "test-real", "release_ready": True}
    raw["items"][0]["source_hash"] = f"real-source-{session_id}"
    lab._write_session(raw)  # type: ignore[attr-defined]
    item_id = session["items"][0]["item_id"]
    lab.write_item_review(
        session_id,
        item_id,
        {"result": "accepted", "rating": 5, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True},
    )
    campaign_store = AudioCampaignStore(audio_lab_store=lab, audio_fix_sprint_store=AudioFixSprintStore(audio_lab_store=lab))
    campaign = campaign_store.create_campaign({"from_session": session_id})
    campaign_id = campaign["campaign_id"]
    campaign_store.signoff(campaign_id, {"signed_by": "QA", "role": "developer"})
    governance = AudioCampaignGovernanceStore(campaign_store=campaign_store)
    return campaign_store, governance, campaign_id


def test_audio_campaign_governance_archive_gate_and_reset(tmp_path: Path, monkeypatch) -> None:
    campaign_store, governance, campaign_id = _signed_campaign(tmp_path, monkeypatch)

    archive = governance.build_archive_zip(campaign_id)
    verification = governance.verify_archive(campaign_id, {"strict": True})
    gate = governance.gate(campaign_id)

    assert archive["status"] == "passed"
    assert verification["status"] == "passed", verification["blockers"]
    assert gate["status"] == "passed"
    with pytest.raises(AudioCampaignGovernanceStateError):
        governance.build_archive_zip(campaign_id)

    cr = governance.create_change_request(campaign_id, {"created_by": "QA", "reason": "Need another listening pass."})
    approved = governance.approve_change_request(campaign_id, cr["change_request_id"], {"approved_by": "Lead"})
    reset = governance.reset_signoff(campaign_id, approved["change_request_id"], {"reason": "Approved reset."})

    assert reset["status"] == "reset"
    assert campaign_store.read_campaign(campaign_id)["status"] == "needs_fix"
    with pytest.raises(AudioCampaignGovernanceStateError):
        governance.reset_signoff(campaign_id, approved["change_request_id"], {"reason": "Reuse should fail."})


def test_audio_campaign_governance_gate_rejects_tampered_verification_report(tmp_path: Path, monkeypatch) -> None:
    _campaign_store, governance, campaign_id = _signed_campaign(tmp_path, monkeypatch)
    governance.build_archive_zip(campaign_id)
    governance.verify_archive(campaign_id, {"strict": True})
    verification_path = governance.archive_verification_report_path(campaign_id)
    verification = read_json(verification_path)
    verification["summary"]["zip_sha256"] = "tampered"
    verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")

    gate = governance.gate(campaign_id)

    assert gate["status"] == "failed"
    assert gate["hard_block"] is True
    assert "integrity failed" in gate["message"]


def test_audio_campaign_archive_verifier_rejects_tamper_and_redaction(tmp_path: Path, monkeypatch) -> None:
    _campaign_store, governance, campaign_id = _signed_campaign(tmp_path, monkeypatch)
    zip_path = Path(governance.build_archive_zip(campaign_id)["zip_path"])

    tampered = tmp_path / "archive-tampered.zip"
    with zipfile.ZipFile(zip_path) as src, zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "governance-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["status"] = "blocked"
                payload["integrity_hash"] = stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
    tamper_report = verify_audio_campaign_archive_package(tampered, strict=True, require_signed=True, require_verification_passed=True)

    redacted = tmp_path / "archive-redaction.zip"
    with zipfile.ZipFile(zip_path) as src, zipfile.ZipFile(redacted, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "README.md":
                data += b"\nsk-secret-value C:\\Users\\demo\\secret.wav\n"
            dst.writestr(info.filename, data)
    redaction_report = verify_audio_campaign_archive_package(redacted, strict=True)

    assert tamper_report["status"] == "failed"
    assert "audio_campaign_archive_governance_binding" in tamper_report["blockers"]
    assert redaction_report["status"] == "failed"
    assert "audio_campaign_archive_redaction_scan" in redaction_report["blockers"]


def test_ga_readiness_requires_external_audio_campaign_archive(tmp_path: Path, monkeypatch) -> None:
    _campaign_store, governance, campaign_id = _signed_campaign(tmp_path, monkeypatch)
    archive_path = Path(governance.build_archive_zip(campaign_id)["zip_path"])
    verification = governance.verify_archive(campaign_id, {"strict": True})
    verification_path = governance.archive_verification_report_path(campaign_id)

    report = build_ga_readiness_report(
        repo_root=tmp_path,
        require_audio_campaign=True,
        audio_campaign_id=campaign_id,
        audio_campaign_archive_zip_path=archive_path,
        audio_campaign_archive_verification_report_path=verification_path,
        allow_dirty=True,
    )
    report_path = write_ga_readiness_report(report, tmp_path / "ga-readiness-report.json")
    ok = verify_ga_readiness_report(
        report_path,
        require_audio_campaign=True,
        audio_campaign_archive_path=archive_path,
        audio_campaign_archive_verification_report_path=verification_path,
    )
    missing_external = verify_ga_readiness_report(report_path, require_audio_campaign=True)

    assert verification["status"] == "passed"
    assert next(item for item in report["checks"] if item["check_id"] == "ga.audio_campaign")["status"] == "passed"
    assert ok["status"] != "failed", ok["blockers"] if "blockers" in ok else ok
    assert missing_external["status"] == "failed"
