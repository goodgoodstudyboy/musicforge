from __future__ import annotations

import re
from typing import Any

from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata
from song_agent.release_metadata import (
    METADATA_BLOCKED_KEYS,
    CREDIT_ROLES,
    release_metadata_source_hash,
)
from song_agent.release_qa import scan_release_payload_for_sensitive_values
from song_agent.releases import ReleaseDocument, stable_hash


RELEASE_METADATA_QA_SCHEMA_VERSION = 1
RELEASE_TYPES = {"single_pack", "ep", "album", "demo_pack"}
UPC_PATTERN = re.compile(r"^\d{12,14}$")
ISRC_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$")
RELEASE_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXPLICIT_WORDS = re.compile(r"(?i)\b(fuck|shit|bitch|explicit)\b")


def build_release_metadata_qa_report(
    *,
    release: ReleaseDocument,
    metadata: dict[str, Any] | None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    metadata = metadata if isinstance(metadata, dict) else {}
    release_checks = _release_checks(release, metadata)
    track_checks = _track_checks(release, metadata)
    blockers = [check for check in [*release_checks, *track_checks] if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check for check in [*release_checks, *track_checks] if check.get("status") == "warning"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    source_hash = release_metadata_source_hash(release, metadata) if metadata else stable_hash({"release_id": release.release_id, "metadata": {}})
    report = {
        "schema_version": RELEASE_METADATA_QA_SCHEMA_VERSION,
        "release_id": release.release_id,
        "generated_at": now,
        "status": status,
        "source_hash": source_hash,
        "checks": release_checks,
        "track_checks": track_checks,
        "blockers": [_check_message(check) for check in blockers],
        "warnings": [_check_message(check) for check in warnings],
        "summary": {
            "status": status,
            "track_count": len(metadata.get("tracks", [])) if isinstance(metadata.get("tracks"), list) else 0,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "source_hash": source_hash,
            "generated_at": now,
        },
    }
    return sanitize_metadata(report, blocked_keys=METADATA_BLOCKED_KEYS)


def release_metadata_qa_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or summary.get("status") or "missing",
            "track_count": summary.get("track_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "source_hash": data.get("source_hash") or summary.get("source_hash"),
            "generated_at": data.get("generated_at") or summary.get("generated_at"),
        },
        blocked_keys=METADATA_BLOCKED_KEYS,
    )


def mark_release_metadata_qa_stale(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> dict[str, Any]:
    data = dict(report or {})
    data["status"] = "stale"
    data["stale"] = True
    if current_source_hash:
        data["current_source_hash"] = current_source_hash
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    summary["status"] = "stale"
    if current_source_hash:
        summary["current_source_hash"] = current_source_hash
    data["summary"] = summary
    return sanitize_metadata(data, blocked_keys=METADATA_BLOCKED_KEYS)


def _release_checks(release: ReleaseDocument, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    if not metadata:
        return [_check("metadata_exists", True, "blocking", "metadata.json is missing.", 1)]
    release_meta = metadata.get("release") if isinstance(metadata.get("release"), dict) else {}
    upc = str(release_meta.get("upc") or "").strip()
    release_date = str(release_meta.get("release_date") or "").strip()
    checks = [
        _check("metadata_exists", False, "blocking", "metadata.json exists.", 0),
        _check("release_title", not str(release_meta.get("title") or "").strip(), "blocking", "Release title is required.", 1),
        _check(
            "release_artist",
            not str(release_meta.get("display_artist") or "").strip() or not str(release_meta.get("primary_artist") or "").strip(),
            "blocking",
            "Release display_artist and primary_artist are required.",
            1,
        ),
        _check("release_type", str(release_meta.get("release_type") or "") not in RELEASE_TYPES, "blocking", "Release type must be supported.", 1),
        _check("release_date_format", bool(release_date and not RELEASE_DATE_PATTERN.fullmatch(release_date)), "warning", "Release date should use YYYY-MM-DD.", 1),
        _check("upc_format", bool(upc and not UPC_PATTERN.fullmatch(upc)), "warning", "UPC should be 12, 13, or 14 digits.", 1),
        _check("copyright_present", not str(release_meta.get("copyright") or "").strip(), "warning", "Copyright line should be filled.", 1),
        _check("phonographic_copyright_present", not str(release_meta.get("phonographic_copyright") or "").strip(), "warning", "P-line should be filled.", 1),
        _check("release_confirmed", not bool(release_meta.get("confirmed", False)), "warning", "Release metadata should be manually confirmed.", 1),
    ]
    findings = scan_release_payload_for_sensitive_values(metadata)
    checks.append(_check("redaction_scan", bool(findings), "blocking", "Release metadata contains sensitive fields or values.", len(findings)))
    return checks


def _track_checks(release: ReleaseDocument, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = metadata.get("tracks") if isinstance(metadata.get("tracks"), list) else []
    release_track_ids = {track.track_id for track in release.tracks}
    metadata_track_ids = {str(item.get("track_id")) for item in tracks if isinstance(item, dict)}
    checks = [
        _track_check(None, "track_count_match", len(tracks) != len(release.tracks), "blocking", "Metadata track count must match release track count.", len(tracks)),
        _track_check(None, "track_id_match", metadata_track_ids != release_track_ids, "blocking", "Metadata track ids must match release track ids.", len(metadata_track_ids)),
    ]
    isrc_values = [str(item.get("isrc") or "").strip().upper() for item in tracks if isinstance(item, dict) and str(item.get("isrc") or "").strip()]
    duplicate_isrc = sorted({value for value in isrc_values if isrc_values.count(value) > 1})
    if duplicate_isrc:
        checks.append(_track_check(None, "isrc_unique", True, "blocking", "ISRC values must be unique across release tracks.", len(duplicate_isrc)))
    else:
        checks.append(_track_check(None, "isrc_unique", False, "blocking", "ISRC values are unique.", 0))
    for item in tracks:
        if not isinstance(item, dict):
            continue
        track_id = str(item.get("track_id") or "unknown")
        isrc = str(item.get("isrc") or "").strip().upper()
        lyrics = str(item.get("lyrics") or "")
        credits = item.get("credits") if isinstance(item.get("credits"), list) else []
        roles = {str(credit.get("role") or "") for credit in credits if isinstance(credit, dict)}
        invalid_roles = [role for role in roles if role and role not in CREDIT_ROLES]
        checks.extend(
            [
                _track_check(track_id, "track_title", not str(item.get("title") or "").strip(), "blocking", "Track title is required.", 1),
                _track_check(track_id, "track_artist", not str(item.get("display_artist") or "").strip(), "blocking", "Track display_artist is required.", 1),
                _track_check(track_id, "isrc_format", bool(isrc and not ISRC_PATTERN.fullmatch(isrc)), "warning", "ISRC should use CCXXXYYNNNNN format.", 1),
                _track_check(track_id, "lyrics_presence", not bool(item.get("instrumental")) and not lyrics.strip(), "warning", "Non-instrumental tracks should include lyrics or a note.", 1),
                _track_check(track_id, "instrumental_lyrics_conflict", bool(item.get("instrumental")) and bool(lyrics.strip()), "warning", "Instrumental track has lyrics.", 1),
                _track_check(track_id, "explicit_flag_consistency", bool(lyrics and EXPLICIT_WORDS.search(lyrics) and not item.get("explicit")), "warning", "Lyrics look explicit but explicit=false.", 1),
                _track_check(track_id, "credits_present", not ({"composer", "producer"} & roles), "warning", "Composer or producer credit should be filled.", 1),
                _track_check(track_id, "credits_role", bool(invalid_roles), "warning", "Credits contain unsupported roles.", len(invalid_roles)),
                _track_check(track_id, "track_confirmed", not bool(item.get("confirmed", False)), "warning", "Track metadata should be manually confirmed.", 1),
            ]
        )
    return checks


def _check(check_id: str, failed: bool, severity: str, message: str, count: int | float | None = 0) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "scope": "release",
            "check_id": check_id,
            "status": "failed" if failed and severity == "blocking" else "warning" if failed else "passed",
            "severity": severity,
            "message": message,
            "count": count,
        },
        blocked_keys=METADATA_BLOCKED_KEYS,
    )


def _track_check(track_id: str | None, check_id: str, failed: bool, severity: str, message: str, count: int | float | None = 0) -> dict[str, Any]:
    data = _check(check_id, failed, severity, message, count)
    data["scope"] = "track"
    if track_id is not None:
        data["track_id"] = track_id
    return sanitize_metadata(data, blocked_keys=METADATA_BLOCKED_KEYS)


def _check_message(check: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "scope": check.get("scope"),
            "check_id": check.get("check_id"),
            "track_id": check.get("track_id"),
            "message": str(check.get("message") or "")[:240],
            "count": check.get("count"),
        },
        blocked_keys=METADATA_BLOCKED_KEYS,
    )
