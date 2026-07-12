from __future__ import annotations

import re
import zipfile
from typing import Iterable

from song_agent.platform.verification.model import build_check

SENSITIVE_BYTE_PATTERNS = (
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(rb"bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\\\\[^\\\r\n]+\\[^\\\r\n]+"),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
)

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
