import pytest

from song_agent.auth import AuthConfig
from song_agent.cli import main


def test_serve_localhost_without_token_starts(monkeypatch):
    seen = {}

    def fake_serve(host, port, auth_config):
        seen["host"] = host
        seen["port"] = port
        seen["auth_config"] = auth_config

    monkeypatch.setattr("song_agent.server.serve", fake_serve)
    monkeypatch.setattr("sys.argv", ["song-agent", "serve", "--host", "127.0.0.1", "--port", "9999"])

    main()

    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 9999
    assert seen["auth_config"] == AuthConfig(enabled=False, token=None)


def test_serve_remote_without_token_exits(monkeypatch, capsys):
    monkeypatch.delenv("MUSICFORGE_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["song-agent", "serve", "--host", "0.0.0.0"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    error = capsys.readouterr().err
    assert "Access token is required" in error


def test_serve_remote_with_cli_token_starts(monkeypatch):
    seen = {}

    def fake_serve(host, port, auth_config):
        seen["auth_config"] = auth_config

    monkeypatch.setenv("MUSICFORGE_ACCESS_TOKEN", "env-local-dev-token")
    monkeypatch.setattr("song_agent.server.serve", fake_serve)
    monkeypatch.setattr(
        "sys.argv",
        [
            "song-agent",
            "serve",
            "--host",
            "0.0.0.0",
            "--access-token",
            "cli-local-dev-token",
        ],
    )

    main()

    assert seen["auth_config"] == AuthConfig(enabled=True, token="cli-local-dev-token")


def test_serve_remote_with_env_token_starts(monkeypatch):
    seen = {}

    def fake_serve(host, port, auth_config):
        seen["auth_config"] = auth_config

    monkeypatch.setenv("MUSICFORGE_ACCESS_TOKEN", "env-local-dev-token")
    monkeypatch.setattr("song_agent.server.serve", fake_serve)
    monkeypatch.setattr("sys.argv", ["song-agent", "serve", "--host", "0.0.0.0"])

    main()

    assert seen["auth_config"] == AuthConfig(enabled=True, token="env-local-dev-token")


def test_serve_rejects_short_token_without_echo(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["song-agent", "serve", "--host", "127.0.0.1", "--access-token", "short"],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "short" not in capsys.readouterr().err
