from __future__ import annotations

from typing import Any

from song_agent.domains.delivery.releases import stable_hash


def audio_campaign_release_track_coverage(tracks: list[Any], case_index: dict[str, Any]) -> dict[str, Any]:
    cases = [case for case in case_index.get("cases", []) if isinstance(case, dict)]
    case_keys = {_case_release_key(case) for case in cases}
    case_keys.discard("")
    rows = []
    missing = []
    for track in sorted(
        tracks,
        key=lambda item: (
            getattr(item, "disc_number", 1),
            getattr(item, "track_number", 1),
            getattr(item, "track_id", ""),
        ),
    ):
        expected = _track_release_key(track)
        matched = bool(expected and expected in case_keys)
        row = {
            "track_id": getattr(track, "track_id", None),
            "track_number": getattr(track, "track_number", None),
            "title": getattr(track, "title", None),
            "project_id": getattr(track, "project_id", None),
            "version_id": getattr(track, "version_id", None),
            "final_export_hash": getattr(track, "final_export_hash", None),
            "identity_key": expected,
            "matched": matched,
        }
        rows.append(row)
        if not matched:
            missing.append(row)
    return {
        "status": "passed" if not missing else "failed",
        "matched_track_count": len(rows) - len(missing),
        "track_count": len(rows),
        "case_count": len(cases),
        "missing_tracks": missing,
    }


def _track_release_key(track: Any) -> str:
    return _identity_key(
        getattr(track, "project_id", ""),
        getattr(track, "version_id", ""),
        getattr(track, "final_export_hash", ""),
    )


def _case_release_key(case: dict[str, Any]) -> str:
    return _identity_key(case.get("project_id"), case.get("version_id"), case.get("final_export_hash"))


def _identity_key(project_id: Any, version_id: Any, final_export_hash: Any) -> str:
    project = str(project_id or "").strip()
    version = str(version_id or "").strip()
    export_hash = str(final_export_hash or "").strip()
    if not (project and version and export_hash):
        return ""
    return stable_hash({"project_id": project, "version_id": version, "final_export_hash": export_hash})
