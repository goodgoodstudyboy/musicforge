"""Compatibility imports for the canonical platform authentication contract."""

from __future__ import annotations

from song_agent.platform.auth import (
    AuthConfig,
    AuthConfigError,
    Mapping as Mapping,
    REMOTE_TOKEN_ERROR,
    build_auth_config,
    dataclass as dataclass,
    hmac as hmac,
    ip_address as ip_address,
    is_loopback_host,
    resolve_access_token,
    validate_access_token,
    validate_bearer_header,
)

__all__ = [
    "AuthConfig",
    "AuthConfigError",
    "REMOTE_TOKEN_ERROR",
    "build_auth_config",
    "is_loopback_host",
    "resolve_access_token",
    "validate_access_token",
    "validate_bearer_header",
]
