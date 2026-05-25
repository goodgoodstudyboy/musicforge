from __future__ import annotations

from pathlib import Path

from song_agent.audio_health import analyze_wav_health, audio_health_allows_release, audio_health_integrity_ok
from tests.audio_fixtures import write_silent_wav, write_test_wav


def test_audio_health_passes_realistic_wav(tmp_path: Path) -> None:
    wav = write_test_wav(tmp_path / "song.wav")

    report = analyze_wav_health(wav, expected_sample_rate=44100, expected_channels=2, expected_bit_depth=16)

    assert report["status"] == "passed"
    assert report["format"]["duration_seconds"] == 9.0
    assert report["metrics"]["peak"] > 0.1
    assert report["wav_sha256"]
    assert audio_health_allows_release(report) is True
    assert audio_health_integrity_ok(report) is True


def test_audio_health_fails_silent_and_invalid_wav(tmp_path: Path) -> None:
    silent = write_silent_wav(tmp_path / "silent.wav")
    invalid = tmp_path / "bad.wav"
    invalid.write_bytes(b"not a wav")

    silent_report = analyze_wav_health(silent)
    invalid_report = analyze_wav_health(invalid)

    assert silent_report["status"] == "failed"
    assert "peak_silent" in silent_report["failures"]
    assert invalid_report["status"] == "failed"
    assert "wav_header" in invalid_report["failures"]
