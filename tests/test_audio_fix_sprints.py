from __future__ import annotations

import pytest

from song_agent.audio_fix_sprints import AudioFixSprintStateError, AudioFixSprintStore
from song_agent.audio_lab import AudioLabStore, write_lab_test_wav
from song_agent.projectio import read_json


def _needs_fix_session(lab: AudioLabStore, *, release_ready_source: bool = False) -> tuple[str, str]:
    smoke = lab.run_smoke({"cases": 1, "render_audio": "auto"})
    session = lab.create_session({"from_smoke": smoke["smoke_run_id"]})
    session_id = session["session_id"]
    item_id = session["items"][0]["item_id"]
    if release_ready_source:
        path = lab.session_path(session_id)
        raw = read_json(path)
        raw["items"][0]["renderer"] = {"runner_kind": "real", "profile_id": "test-real", "release_ready": True}
        raw["items"][0]["source_hash"] = "release-ready-source"
        lab._write_session(raw)  # type: ignore[attr-defined]
    lab.write_item_review(
        session_id,
        item_id,
        {"result": "needs_fix", "rating": 2, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True},
    )
    lab.add_marker(session_id, item_id, {"time_seconds": 1.2, "category": "mix_balance", "severity": "high", "message": "Hook is masked."})
    return session_id, item_id


def _review_select_and_recheck(store: AudioFixSprintStore, sprint_id: str) -> dict:
    sprint = store.read_sprint(sprint_id)
    item_id = sprint["items"][0]["fix_item_id"]
    candidate = store.generate_candidates(sprint_id)["candidates"][0]
    with pytest.raises(AudioFixSprintStateError):
        store.select_candidate(sprint_id, item_id, candidate["candidate_id"])
    store.review_candidate(
        sprint_id,
        item_id,
        candidate["candidate_id"],
        {"preferred": "right", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True},
    )
    store.select_candidate(sprint_id, item_id, candidate["candidate_id"])
    recheck = store.create_recheck_session(sprint_id)["recheck_session"]
    store.review_recheck_item(
        sprint_id,
        recheck["items"][0]["item_id"],
        {"result": "accepted", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True},
    )
    return store.closeout_report(sprint_id)


def test_audio_fix_sprint_blocks_test_fake_closeout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    session_id, _ = _needs_fix_session(lab)
    store = AudioFixSprintStore(audio_lab_store=lab, wav_writer=write_lab_test_wav)

    sprint = store.create_sprint({"from_session": session_id, "include_test_audio": True})
    closeout = _review_select_and_recheck(store, sprint["fix_sprint_id"])

    assert closeout["status"] == "failed"
    assert "test_fake_audio_not_release_ready" in closeout["blockers"]
    with pytest.raises(AudioFixSprintStateError):
        store.close_sprint(sprint["fix_sprint_id"])


def test_audio_fix_sprint_closes_after_manual_real_recheck(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    session_id, _ = _needs_fix_session(lab, release_ready_source=True)
    store = AudioFixSprintStore(audio_lab_store=lab)

    sprint = store.create_sprint({"from_session": session_id})
    closeout = _review_select_and_recheck(store, sprint["fix_sprint_id"])
    result = store.close_sprint(sprint["fix_sprint_id"], {"closed_by": "QA"})

    assert closeout["status"] == "passed"
    assert closeout["summary"]["release_ready_audio_count"] == 1
    assert result["sprint"]["status"] == "closed"


def test_audio_fix_sprint_detects_source_stale(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    session_id, item_id = _needs_fix_session(lab, release_ready_source=True)
    store = AudioFixSprintStore(audio_lab_store=lab)

    sprint = store.create_sprint({"from_session": session_id})
    lab.add_marker(session_id, item_id, {"time_seconds": 2.0, "category": "timing", "severity": "high", "message": "Late snare."})
    refreshed = store.refresh_sprint(sprint["fix_sprint_id"])

    assert refreshed["stale"] is True
    assert "source_session_changed" in refreshed["stale_reasons"]
    with pytest.raises(AudioFixSprintStateError):
        store.generate_candidates(sprint["fix_sprint_id"])


def test_audio_fix_sprint_sanitizes_manual_text_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lab = AudioLabStore(wav_writer=write_lab_test_wav)
    session_id, _ = _needs_fix_session(lab, release_ready_source=True)
    store = AudioFixSprintStore(audio_lab_store=lab)
    secret_text = r"sk-secret-value api_key=secret-value C:\Users\demo\secret.wav"

    sprint = store.create_sprint({"from_session": session_id, "name": f"Sprint {secret_text}"})
    sprint_id = sprint["fix_sprint_id"]
    item_id = sprint["items"][0]["fix_item_id"]
    candidate = store.generate_candidates(sprint_id)["candidates"][0]
    store.review_candidate(
        sprint_id,
        item_id,
        candidate["candidate_id"],
        {
            "preferred": "right",
            "rating": 4,
            "reviewer": {"name": f"QA {secret_text}", "role": f"developer {secret_text}"},
            "notes": f"Candidate note {secret_text}",
            "playback_confirmed": True,
        },
    )
    store.select_candidate(sprint_id, item_id, candidate["candidate_id"], {"selected_by": f"selector {secret_text}"})
    recheck = store.create_recheck_session(sprint_id)["recheck_session"]
    store.review_recheck_item(
        sprint_id,
        recheck["items"][0]["item_id"],
        {
            "result": "accepted",
            "rating": 4,
            "reviewer": {"name": f"Recheck {secret_text}", "role": f"reviewer {secret_text}"},
            "notes": f"Recheck note {secret_text}",
            "playback_confirmed": True,
        },
    )
    store.close_sprint(sprint_id, {"closed_by": f"closer {secret_text}"})

    raw = read_json(store.sprint_dir(sprint_id) / "sprint.json")
    serialized = str(raw)
    assert "sk-secret-value" not in serialized
    assert "api_key=secret-value" not in serialized
    assert r"C:\Users\demo\secret.wav" not in serialized
    assert "sk-[REDACTED]" in serialized
    assert "[REDACTED]" in serialized
    assert "[REDACTED_LOCAL_PATH]" in serialized
