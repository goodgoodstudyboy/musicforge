from __future__ import annotations

from pathlib import Path

from song_agent.audio_lab import AudioLabStore, AudioLabValidationError, write_lab_test_wav
from song_agent.projectio import read_json


def test_audio_lab_environment_and_midi_only_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AudioLabStore()

    env = store.environment_status()
    smoke = store.run_smoke({"cases": 1, "render_audio": "never"})

    assert env["status"] == "missing"
    assert env["summary"]["real_audio_ready"] is False
    assert smoke["status"] == "warning"
    assert smoke["summary"]["midi_count"] == 1
    assert smoke["summary"]["wav_count"] == 0
    assert smoke["items"][0]["audio_status"] == "skipped_by_request"
    assert "soundfont_path" not in str(env)


def test_audio_lab_required_audio_fails_without_renderer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AudioLabStore()

    smoke = store.run_smoke({"cases": 1, "render_audio": "required"})

    assert smoke["status"] == "failed"
    assert smoke["items"][0]["audio_status"] in {"failed", "skipped_renderer_not_configured"}
    assert smoke["summary"]["failed_count"] == 1


def test_audio_lab_session_review_marker_and_stale_guard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AudioLabStore(wav_writer=write_lab_test_wav)
    smoke = store.run_smoke({"cases": 1, "render_audio": "auto"})
    session = store.create_session({"from_smoke": smoke["smoke_run_id"]})
    item_id = session["items"][0]["item_id"]

    try:
        store.write_item_review(session["session_id"], item_id, {"result": "accepted", "rating": 4, "reviewer": {"name": "QA", "role": "developer"}})
        raise AssertionError("missing playback_confirmed should fail")
    except AudioLabValidationError as exc:
        assert "playback_confirmed" in str(exc)

    reviewed = store.write_item_review(
        session["session_id"],
        item_id,
        {"result": "needs_fix", "rating": 2, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True, "notes": "Bass is too loud."},
    )
    marker = store.add_marker(reviewed["session"]["session_id"], item_id, {"time_seconds": 2.0, "category": "mix_balance", "severity": "high", "message": "Bass masks hook."})
    draft = store.create_marker_draft(reviewed["session"]["session_id"], marker["marker"]["marker_id"], "review_task", {})
    report = store.session_report(reviewed["session"]["session_id"])
    closed = store.close_session(reviewed["session"]["session_id"], {"closed_by": "QA"})

    assert reviewed["review"]["review_mode"] == "manual"
    assert reviewed["review"]["audio_evidence"]["wav_sha256"] == smoke["items"][0]["artifact_hashes"]["wav_sha256"]
    assert marker["marker"]["category"] == "mix_balance"
    assert draft["draft"]["status"] == "draft"
    assert draft["draft"]["auto_apply"] is False
    assert report["summary"]["needs_fix_count"] == 1
    assert report["summary"]["test_fake_count"] == 1
    assert report["summary"]["release_ready_audio_count"] == 0
    assert report["summary"]["test_fake_audio_not_release_ready"] is True
    assert closed["session"]["status"] == "closed_needs_fix"
    assert closed["summary"]["status"] == "closed_needs_fix"

    wav_rel = smoke["items"][0]["artifact_relpaths"]["wav"]
    wav_path = Path(".musicforge") / "audio-lab" / wav_rel
    wav_path.write_bytes(wav_path.read_bytes() + b"tamper")
    stale = store.read_session(reviewed["session"]["session_id"])
    assert stale["items"][0]["stale"] is True
    assert "wav_changed" in stale["items"][0]["stale_reasons"]


def test_audio_lab_accepted_only_session_closes_normally(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AudioLabStore(wav_writer=write_lab_test_wav)
    smoke = store.run_smoke({"cases": 1, "render_audio": "auto"})
    session = store.create_session({"from_smoke": smoke["smoke_run_id"]})
    item_id = session["items"][0]["item_id"]

    store.write_item_review(
        session["session_id"],
        item_id,
        {"result": "accepted", "rating": 5, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True},
    )
    closed = store.close_session(session["session_id"], {"closed_by": "QA"})

    assert closed["session"]["status"] == "closed"
    assert closed["summary"]["accepted_count"] == 1
    assert closed["summary"]["needs_fix_count"] == 0
    assert closed["summary"]["test_fake_count"] == 1


def test_audio_lab_ab_comparison_binds_artifact_hashes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    dummy_midi = tmp_path / "dummy.mid"
    dummy_midi.write_bytes(b"MThd")
    left = write_lab_test_wav(dummy_midi, tmp_path / "left.wav")
    right = write_lab_test_wav(dummy_midi, tmp_path / "right.wav", amplitude=0.1)
    store = AudioLabStore()

    comparison = store.create_comparison({"left": str(left), "right": str(right)})
    reviewed = store.review_comparison(
        comparison["comparison_id"],
        {"preferred": "right", "rating": 4, "rating_delta": 1, "reviewer": {"name": "QA", "role": "developer"}, "playback_confirmed": True},
    )
    report = store.comparison_report(comparison["comparison_id"])

    raw = read_json(Path(".musicforge") / "audio-lab" / "comparisons" / comparison["comparison_id"] / "comparison.json")
    assert raw["left"]["source_abspath"]
    assert "source_abspath" not in reviewed["left"]
    assert reviewed["review"]["preferred"] == "right"
    assert report["status"] == "passed"
