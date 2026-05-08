from __future__ import annotations

import re
from typing import Any


DEFAULT_BLOCKED_METADATA_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "path",
    "raw_provider_response",
    "secret",
    "token",
}

SENSITIVE_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_[REDACTED]"),
    (re.compile(r"ghp_[A-Za-z0-9_]{20,}"), "ghp_[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "sk-[REDACTED]"),
    (re.compile(r"(?i)Authorization\s*:\s*Bearer\s+[^\s,;]+"), "[REDACTED]"),
    (re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,;]+"), "[REDACTED]"),
    (re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s,;]+(?:[\\/]+[^\s,;]+)*"), "[REDACTED_LOCAL_PATH]"),
    (re.compile(r"(?<!\S)/Users/[^/\s,;]+(?:/[^\s,;]+)*"), "[REDACTED_LOCAL_PATH]"),
    (re.compile(r"(?<!\S)/home/[^/\s,;]+(?:/[^\s,;]+)*"), "[REDACTED_LOCAL_PATH]"),
)


def sanitize_sensitive_text(value: str) -> str:
    text = _strip_unsafe_control_chars(str(value))
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_metadata(value: Any, *, blocked_keys: set[str] | None = None) -> Any:
    blocked = blocked_keys or DEFAULT_BLOCKED_METADATA_KEYS
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in blocked:
                continue
            cleaned[str(key)] = sanitize_metadata(item, blocked_keys=blocked)
        return cleaned
    if isinstance(value, list):
        return [sanitize_metadata(item, blocked_keys=blocked) for item in value]
    if isinstance(value, str):
        return sanitize_sensitive_text(value)
    return value


def _strip_unsafe_control_chars(value: str) -> str:
    return "".join(char for char in value if char == "\n" or char == "\t" or ord(char) >= 32)
