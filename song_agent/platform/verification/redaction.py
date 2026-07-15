from __future__ import annotations

import re
import zipfile
from typing import Any, Iterable

from song_agent.platform.verification.model import build_check

SENSITIVE_BYTE_PATTERNS = (
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(rb"bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\\\\[^\\\r\n]+\\[^\\\r\n]+"),
    re.compile(rb"(?<![A-Za-z0-9_])/(?:Users|home|tmp|var/tmp|private/tmp|mnt/[A-Za-z])/[^/\s,;\"'{}\[\]()]+(?:/[^/\s,;\"'{}\[\]()]+)*"),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
)

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
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{6,}"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,;]+"), "[REDACTED]"),
    (re.compile(r"(?i)\b[A-Z]:[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "[REDACTED_LOCAL_PATH]"),
    (re.compile(r"(?<![\\/\w])(?:\\\\|(?<!:)//)[^\\/\s,;]+[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "[REDACTED_LOCAL_PATH]"),
    (
        re.compile(r"(?<![A-Za-z0-9_])/(?:Users|home|tmp|var/tmp|private/tmp|mnt/[A-Za-z])/[^/\s,;\"'{}\[\]()]+(?:/[^/\s,;\"'{}\[\]()]+)*"),
        "[REDACTED_LOCAL_PATH]",
    ),
)


def sanitize_sensitive_text(value: str) -> str:
    text = _strip_unsafe_control_chars(str(value))
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_metadata(value: Any, *, blocked_keys: set[str] | None = None) -> Any:
    blocked = blocked_keys or DEFAULT_BLOCKED_METADATA_KEYS
    if isinstance(value, dict):
        return {
            str(key): sanitize_metadata(item, blocked_keys=blocked)
            for key, item in value.items()
            if str(key).lower() not in blocked
        }
    if isinstance(value, list):
        return [sanitize_metadata(item, blocked_keys=blocked) for item in value]
    if isinstance(value, str):
        return sanitize_sensitive_text(value)
    return value


def _strip_unsafe_control_chars(value: str) -> str:
    return "".join(char for char in value if char in {"\n", "\t"} or ord(char) >= 32)

def archive_redaction_check(
    archive: zipfile.ZipFile,
    names: Iterable[str],
    *,
    check_id: str,
    suffixes: tuple[str, ...] = (".json", ".jsonl", ".txt", ".md", ".html"),
) -> dict[str, object]:
    offenders: list[str] = []
    for name in names:
        if not name.lower().endswith(suffixes):
            continue
        data = archive.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_BYTE_PATTERNS):
            offenders.append(name)
    return build_check(
        check_id,
        not offenders,
        "Package contains no obvious secrets or local paths.",
        {"offenders": sorted(set(offenders))},
    )
