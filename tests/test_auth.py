import pytest

from song_agent.auth import (
    AuthConfigError,
    build_auth_config,
    is_loopback_host,
    resolve_access_token,
    validate_bearer_header,
)


def test_is_loopback_host() -> None:
    assert is_loopback_host("127.0.0.1") is True
    assert is_loopback_host("localhost") is True
    assert is_loopback_host("::1") is True
    assert is_loopback_host("[::1]") is True
    assert is_loopback_host("0.0.0.0") is False
    assert is_loopback_host("::") is False
    assert is_loopback_host("192.168.1.10") is False


def test_localhost_without_token_disables_auth() -> None:
    config = build_auth_config("127.0.0.1", None, {})

    assert config.enabled is False
    assert config.token is None


def test_remote_host_without_token_rejects_startup() -> None:
    with pytest.raises(AuthConfigError, match="Access token is required"):
        build_auth_config("0.0.0.0", None, {})


def test_remote_host_with_cli_token_enables_auth() -> None:
    config = build_auth_config("0.0.0.0", "local-dev-token-123", {})

    assert config.enabled is True
    assert config.token == "local-dev-token-123"


def test_remote_host_with_env_token_enables_auth() -> None:
    config = build_auth_config(
        "192.168.1.10",
        None,
        {"MUSICFORGE_ACCESS_TOKEN": "env-local-dev-token"},
    )

    assert config.enabled is True
    assert config.token == "env-local-dev-token"


def test_cli_token_preempts_env_token() -> None:
    token = resolve_access_token(
        "cli-local-dev-token",
        {"MUSICFORGE_ACCESS_TOKEN": "env-local-dev-token"},
    )

    assert token == "cli-local-dev-token"


def test_token_quality_errors_do_not_echo_token() -> None:
    with pytest.raises(AuthConfigError) as short_exc:
        resolve_access_token("too-short", {})

    assert "too-short" not in str(short_exc.value)

    with pytest.raises(AuthConfigError) as newline_exc:
        resolve_access_token("valid-token-value\nsecret", {})

    assert "valid-token-value" not in str(newline_exc.value)


def test_validate_bearer_header() -> None:
    token = "local-dev-token-123"

    assert validate_bearer_header(f"Bearer {token}", token) is True
    assert validate_bearer_header(None, token) is False
    assert validate_bearer_header("", token) is False
    assert validate_bearer_header("Basic abc", token) is False
    assert validate_bearer_header("Bearer wrong-token-value", token) is False
