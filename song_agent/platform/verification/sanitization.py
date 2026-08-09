from __future__ import annotations

import re
from typing import TypeVar, cast

from song_agent.platform.contracts.documents import normalize_json_value


VERIFICATION_BLOCKED_METADATA_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "path",
    "provider_snapshot",
    "raw_provider_response",
    "secret",
    "token",
}
DEFAULT_BLOCKED_METADATA_KEYS = VERIFICATION_BLOCKED_METADATA_KEYS

SENSITIVE_TEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_[REDACTED]"),
    (re.compile(r"ghp_[A-Za-z0-9_]{20,}"), "ghp_[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "sk-[REDACTED]"),
    (re.compile(r"(?i)Authorization\s*:\s*Bearer\s+[^\s,;]+"), "[REDACTED]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{6,}"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,;]+"), "[REDACTED]"),
    (re.compile(r"(?i)\b[A-Z]:[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "[REDACTED_LOCAL_PATH]"),
    (re.compile(r"(?<![\\/\w])(?:\\\\|(?<!:)//)[^\\/\s,;]+[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "[REDACTED_LOCAL_PATH]"),
    (
        re.compile(r"(?<![A-Za-z0-9_])/(?:Users|home|tmp|var/tmp|private/tmp|mnt/[A-Za-z])/[^/\s,;\"'{}\[\]()]+(?:/[^/\s,;\"'{}\[\]()]+)*"),
        "[REDACTED_LOCAL_PATH]",
    ),
)


_ValueT = TypeVar("_ValueT")


def sanitize_sensitive_text(value: str) -> str:
    text = "".join(char for char in str(value) if char in {"\n", "\t"} or ord(char) >= 32)
    for pattern, replacement in SENSITIVE_TEXT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_metadata(value: _ValueT, *, blocked_keys: set[str] | None = None) -> _ValueT:
    blocked = blocked_keys or VERIFICATION_BLOCKED_METADATA_KEYS
    if isinstance(value, dict):
        sanitized = {
            str(key): sanitize_metadata(item, blocked_keys=blocked)
            for key, item in value.items()
            if str(key).lower() not in blocked
        }
        return cast(_ValueT, sanitized)
    if isinstance(value, list):
        return cast(_ValueT, [sanitize_metadata(item, blocked_keys=blocked) for item in value])
    if isinstance(value, str):
        return cast(_ValueT, sanitize_sensitive_text(value))
    return cast(_ValueT, normalize_json_value(value))
