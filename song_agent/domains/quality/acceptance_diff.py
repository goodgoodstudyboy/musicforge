from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

from typing import Any as Any

from song_agent.platform.verification.redaction import sanitize_metadata as sanitize_metadata


ACCEPTANCE_DIFF_SCHEMA_VERSION = 1


def build_acceptance_diff(left_report: DomainDocument, right_report: DomainDocument) -> DomainDocument:
    left_cases = _cases_by_song(left_report)
    right_cases = _cases_by_song(right_report)
    song_ids = sorted(set(left_cases) | set(right_cases))
    rows: list[ImplementationDocument] = []
    blockers: list[str] = []
    for song_id in song_ids:
        left = left_cases.get(song_id, {})
        right = right_cases.get(song_id, {})
        row: ImplementationDocument = {
            "song_id": song_id,
            "left_case_id": left.get("case_id"),
            "right_case_id": right.get("case_id"),
            "status": _row_status(left, right),
            "quality_delta": _delta(left.get("quality_overall"), right.get("quality_overall")),
            "note_count_delta": _delta(left.get("note_count"), right.get("note_count")),
            "track_count_delta": _delta(left.get("track_count"), right.get("track_count")),
            "section_count_delta": _delta(left.get("section_count"), right.get("section_count")),
            "rating_delta": _delta(left.get("rating"), right.get("rating")),
            "health_status": {"left": left.get("health_status"), "right": right.get("health_status")},
            "review_status": {"left": left.get("review_status"), "right": right.get("review_status")},
            "new_blockers": sorted(set(right.get("health_blockers", [])) - set(left.get("health_blockers", []))),
            "resolved_blockers": sorted(set(left.get("health_blockers", [])) - set(right.get("health_blockers", []))),
        }
        if row["new_blockers"]:
            blockers.append(f"{song_id}: new health blockers")
        if isinstance(row["rating_delta"], (int, float)) and row["rating_delta"] < 0:
            blockers.append(f"{song_id}: rating regressed")
        rows.append(row)
    return sanitize_metadata(
        {
            "schema_version": ACCEPTANCE_DIFF_SCHEMA_VERSION,
            "status": "failed" if blockers else "passed",
            "left_suite_id": left_report.get("suite_id"),
            "right_suite_id": right_report.get("suite_id"),
            "summary": {
                "song_count": len(song_ids),
                "missing_left": sum(1 for row in rows if row["status"] == "missing_left"),
                "missing_right": sum(1 for row in rows if row["status"] == "missing_right"),
                "new_blocker_count": sum(len(row["new_blockers"]) for row in rows),
                "rating_regression_count": sum(
                    1 for row in rows if isinstance(row["rating_delta"], (int, float)) and row["rating_delta"] < 0
                ),
            },
            "songs": rows,
            "blockers": blockers,
        }
    )


def _cases_by_song(report: ImplementationDocument) -> dict[str, ImplementationDocument]:
    rows = {}
    for case in report.get("cases", []) if isinstance(report.get("cases"), list) else []:
        if not isinstance(case, dict):
            continue
        song_id = str(case.get("song_id") or case.get("case_id") or "").strip()
        if song_id:
            rows[song_id] = case
    return rows


def _row_status(left: ImplementationDocument, right: ImplementationDocument) -> str:
    if not left:
        return "missing_left"
    if not right:
        return "missing_right"
    return "matched"


def _delta(left: Any, right: Any) -> float | int | None:
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return None
    value = right - left
    return round(value, 3) if isinstance(value, float) else value
