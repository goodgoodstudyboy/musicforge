from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument
from typing import Iterable

from song_agent.platform.contracts.evidence import EvidenceRef
from song_agent.platform.verification.manifest import safe_check_key
from song_agent.platform.verification.model import build_check


def evidence_identity_checks(
    expected: Iterable[EvidenceRef],
    actual: Iterable[EvidenceRef],
    *,
    check_prefix: str,
) -> list[DomainDocument]:
    expected_rows = list(expected)
    actual_rows = list(actual)
    expected_by_key = {row.identity: row for row in expected_rows}
    actual_by_key = {row.identity: row for row in actual_rows}
    missing = sorted("|".join(map(str, key)) for key in set(expected_by_key) - set(actual_by_key))
    extra = sorted("|".join(map(str, key)) for key in set(actual_by_key) - set(expected_by_key))
    checks = [
        build_check(
            f"{check_prefix}_expected_identity_unique",
            len(expected_by_key) == len(expected_rows),
            "Expected external evidence identities are unique.",
        ),
        build_check(
            f"{check_prefix}_actual_identity_unique",
            len(actual_by_key) == len(actual_rows),
            "Actual external evidence identities are unique.",
        ),
        build_check(f"{check_prefix}_identity", not missing and not extra, "External evidence identities match.", {"missing": missing, "extra": extra}),
    ]
    for key, expected_row in expected_by_key.items():
        actual_row = actual_by_key.get(key)
        if actual_row is None:
            continue
        label = safe_check_key("_".join(str(part) for part in key))
        for field in ("package_type", "zip_sha256", "zip_size_bytes", "manifest_hash", "verification_report_hash", "source_hash", "signoff_hash", "history_event_hash"):
            expected_value = getattr(expected_row, field)
            actual_value = getattr(actual_row, field)
            checks.append(build_check(f"{check_prefix}_{label}_{field}", not expected_value or expected_value == actual_value, f"External evidence {field} matches.", {"identity": key}))
    return checks
