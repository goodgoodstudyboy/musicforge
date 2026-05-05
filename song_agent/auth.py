from __future__ import annotations

import hmac
from dataclasses import dataclass
from ipaddress import ip_address
from collections.abc import Mapping


REMOTE_TOKEN_ERROR = (
    "Access token is required when binding MusicForge Studio to a non-localhost host. "
    "Use --access-token or MUSICFORGE_ACCESS_TOKEN."
)


class AuthConfigError(ValueError):
    """Raised when access-token configuration is invalid."""


@dataclass(frozen=True)
class AuthConfig:
    enabled: bool
    token: str | None = None


def is_loopback_host(host: str) -> bool:
    host = (host or "").strip().strip("[]").lower()
    if host == "localhost":
        return True
    if not host:
        return False
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def resolve_access_token(
    cli_token: str | None,
    environ: Mapping[str, str],
) -> str | None:
    raw_token = cli_token if cli_token is not None else environ.get("MUSICFORGE_ACCESS_TOKEN")
    if raw_token is None:
        return None
    token = raw_token.strip()
    validate_access_token(token)
    return token


def build_auth_config(
    host: str,
    cli_token: str | None,
    environ: Mapping[str, str],
) -> AuthConfig:
    token = resolve_access_token(cli_token, environ)
    if token:
        return AuthConfig(enabled=True, token=token)
    if is_loopback_host(host):
        return AuthConfig(enabled=False, token=None)
    raise AuthConfigError(REMOTE_TOKEN_ERROR)


def validate_access_token(token: str) -> None:
    if not token:
        raise AuthConfigError("Access token must not be empty.")
    if "\n" in token or "\r" in token:
        raise AuthConfigError("Access token must not contain line breaks.")
    if len(token) < 16:
        raise AuthConfigError("Access token must be at least 16 characters.")


def validate_bearer_header(header_value: str | None, token: str) -> bool:
    if not header_value:
        return False
    prefix = "Bearer "
    if not header_value.startswith(prefix):
        return False
    candidate = header_value[len(prefix) :].strip()
    if not candidate:
        return False
    return hmac.compare_digest(candidate, token)
