import pytest

from song_agent.cli import main
from song_agent.provider import ProviderConfig, save_provider_config


def test_doctor_without_provider_returns_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["song-agent", "doctor"])

    main()

    output = capsys.readouterr().out
    assert "MusicForge doctor" in output
    assert "provider config: missing" in output
    assert "local deterministic mode: ok" in output


def test_doctor_reports_provider_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    save_provider_config(ProviderConfig(base_url="https://api.example.com/v1", model="main"))
    monkeypatch.setattr("sys.argv", ["song-agent", "doctor"])

    main()

    output = capsys.readouterr().out
    assert "provider config: warning incomplete" in output


def test_doctor_provider_test_with_mock(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    save_provider_config(ProviderConfig(wire_api="mock", model="mock-main"))
    monkeypatch.setattr("sys.argv", ["song-agent", "doctor", "--provider-test"])

    main()

    output = capsys.readouterr().out
    assert "provider config: configured (mock, model=mock-main, key=-)" in output
    assert "provider test: ok (mock)" in output


def test_doctor_provider_test_failure_does_not_raise(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    save_provider_config(ProviderConfig(base_url="https://api.example.com/v1", model="main"))
    monkeypatch.setattr("sys.argv", ["song-agent", "doctor", "--provider-test"])

    main()

    output = capsys.readouterr().out
    assert "provider test: failed" in output
