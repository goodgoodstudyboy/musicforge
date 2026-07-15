from __future__ import annotations

from typing import Any

from song_agent.domains.quality.music_acceptance import stable_hash


GA_READINESS_PACKAGE_TYPE = "musicforge_ga_readiness_report"


GA_READINESS_SCHEMA_VERSION = 1


def ga_readiness_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})


def ga_readiness_integrity_ok(report: dict[str, Any]) -> bool:
    expected = str(report.get("integrity_hash") or "")
    return bool(expected) and expected == ga_readiness_integrity_hash(report)
