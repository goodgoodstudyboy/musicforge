from __future__ import annotations

from song_agent.platform.contracts import DomainDocument

from song_agent.domains.quality.music_acceptance import stable_hash


GA_READINESS_PACKAGE_TYPE = "musicforge_ga_readiness_report"


GA_READINESS_SCHEMA_VERSION = 1


def ga_readiness_integrity_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})


def ga_readiness_integrity_ok(report: DomainDocument) -> bool:
    expected = str(report.get("integrity_hash") or "")
    return bool(expected) and expected == ga_readiness_integrity_hash(report)
