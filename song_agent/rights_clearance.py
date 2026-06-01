from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.release_metadata import read_release_metadata
from song_agent.releases import BLOCKED_RELEASE_KEYS, ReleaseStateError, ReleaseStore, stable_hash


RIGHTS_SCHEMA_VERSION = 1
RIGHTS_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}
RIGHTS_REPORT_INTEGRITY_EXCLUDE = {"integrity_hash", "integrity_ok", "stale", "stale_reasons", "current_source_hash"}
RIGHTS_TRACK_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons"}
RIGHTS_SUMMARY_INTEGRITY_EXCLUDE = {"summary_hash"}
CONTRIBUTOR_ROLES_REQUIRING_SPLITS = {"composer", "lyricist"}
SOURCE_BLOCKING_STATUSES = {"uncleared", "blocked", "unknown", "pending"}
SOURCE_SAFE_STATUSES = {"cleared", "waived", "owned", "public_domain", "original"}


class RightsClearanceError(ValueError):
    pass


class RightsClearanceNotFoundError(RightsClearanceError):
    pass


class RightsClearanceStateError(RightsClearanceError):
    pass


class RightsClearanceStore:
    def __init__(self, release_store: ReleaseStore) -> None:
        self.release_store = release_store

    def rights_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "rights"

    def parties_path(self, release_id: str) -> Path:
        return self.rights_dir(release_id) / "parties.json"

    def report_path(self, release_id: str) -> Path:
        return self.rights_dir(release_id) / "report.json"

    def tracks_dir(self, release_id: str) -> Path:
        return self.rights_dir(release_id) / "tracks"

    def track_path(self, release_id: str, track_id: str) -> Path:
        return self.tracks_dir(release_id) / f"{_safe_id(track_id, 'track')}.json"

    def events_path(self, release_id: str) -> Path:
        return self.rights_dir(release_id) / "events.jsonl"

    def list_parties(self, release_id: str) -> list[dict[str, Any]]:
        self.release_store.get_release(release_id)
        data = _read_json_default(self.parties_path(release_id), {"parties": []})
        parties = data.get("parties") if isinstance(data.get("parties"), list) else []
        return [sanitize_metadata(item, blocked_keys=RIGHTS_BLOCKED_KEYS) for item in parties if isinstance(item, dict)]

    def upsert_party(self, release_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_mutable(release_id)
        data = _read_json_default(self.parties_path(release_id), {"schema_version": RIGHTS_SCHEMA_VERSION, "release_id": release_id, "parties": []})
        parties = data.get("parties") if isinstance(data.get("parties"), list) else []
        party_id = _safe_id(str(payload.get("party_id") or ""), "party") if str(payload.get("party_id") or "").strip() else _next_id(parties, "rparty", "party_id")
        party = sanitize_metadata(
            {
                "party_id": party_id,
                "display_name": _text(payload.get("display_name") or payload.get("name"), 180),
                "public_credit_name": _text(payload.get("public_credit_name") or payload.get("display_name") or payload.get("name"), 180),
                "legal_name": _text(payload.get("legal_name"), 180),
                "role_notes": _text(payload.get("role_notes") or payload.get("notes"), 500),
                "contact": _safe_dict(payload.get("contact")),
                "identifiers": _safe_dict(payload.get("identifiers")),
                "created_at": now,
                "updated_at": now,
            },
            blocked_keys=RIGHTS_BLOCKED_KEYS,
        )
        if not party["display_name"]:
            raise RightsClearanceError("party display_name is required.")
        replaced = False
        next_parties: list[dict[str, Any]] = []
        for item in parties:
            if isinstance(item, dict) and str(item.get("party_id") or "") == party_id:
                party["created_at"] = item.get("created_at") or now
                next_parties.append(party)
                replaced = True
            elif isinstance(item, dict):
                next_parties.append(item)
        if not replaced:
            next_parties.append(party)
        write_json(self.parties_path(release_id), sanitize_metadata({**data, "schema_version": RIGHTS_SCHEMA_VERSION, "release_id": release_id, "updated_at": now, "parties": sorted(next_parties, key=lambda row: str(row.get("party_id") or ""))}, blocked_keys=RIGHTS_BLOCKED_KEYS))
        self._append_event(release_id, "rights_party_upserted", {"party_id": party_id}, now)
        self._mark_export_stale(release_id, "rights_party_changed")
        return party

    def read_track(self, release_id: str, track_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        self.release_store.get_release(release_id)
        path = self.track_path(release_id, track_id)
        if not path.exists():
            if default is not None:
                return default
            raise RightsClearanceNotFoundError(f"Rights track record not found: {track_id}.")
        return sanitize_metadata(read_json(path), blocked_keys=RIGHTS_BLOCKED_KEYS)

    def upsert_track(self, release_id: str, track_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_mutable(release_id)
        release = self.release_store.get_release(release_id)
        track = _release_track(release, track_id)
        if track is None:
            raise RightsClearanceNotFoundError(f"Release track not found: {track_id}.")
        existing = self.read_track(release_id, track_id, default={})
        metadata = _metadata_track(self.release_store, release_id, track_id)
        merged = {
            **existing,
            "schema_version": RIGHTS_SCHEMA_VERSION,
            "release_id": release_id,
            "track_id": track_id,
            "updated_at": now,
            "track_snapshot": _track_snapshot(track),
            "metadata_snapshot": _metadata_snapshot(metadata),
        }
        if "contributors" in payload:
            merged["contributors"] = [_normalize_contributor(item) for item in _list(payload.get("contributors"))]
        if "source_usages" in payload:
            merged["source_usages"] = [_normalize_source_usage(item) for item in _list(payload.get("source_usages"))]
        for key in ("instrumental", "notes", "metadata_credits_waived", "copyright_owner_note"):
            if key in payload:
                merged[key] = payload.get(key)
        source_hash = rights_track_source_hash(merged)
        merged["source_hash"] = source_hash
        merged["stale"] = False
        merged["stale_reasons"] = []
        merged["integrity_hash"] = rights_track_integrity_hash(merged)
        clean = sanitize_metadata(merged, blocked_keys=RIGHTS_BLOCKED_KEYS)
        write_json(self.track_path(release_id, track_id), clean)
        self._append_event(release_id, "rights_track_upserted", {"track_id": track_id}, now)
        self._mark_export_stale(release_id, "rights_track_changed")
        return clean

    def review_track(self, release_id: str, track_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_mutable(release_id)
        record = self.read_track(release_id, track_id, default={})
        if not record:
            record = self.upsert_track(release_id, track_id, {}, now=now)
        status = str(payload.get("status") or payload.get("clearance_status") or "accepted").strip().lower()
        if status not in {"accepted", "waived", "needs_work", "rejected"}:
            raise RightsClearanceError("Unsupported rights review status.")
        review = sanitize_metadata(
            {
                "status": status,
                "review_mode": str(payload.get("review_mode") or "manual").strip().lower(),
                "confirmed_by": _text(payload.get("confirmed_by") or payload.get("reviewer") or payload.get("signed_by"), 160),
                "confirmed_at": now,
                "playback_or_metadata_checked": bool(payload.get("playback_or_metadata_checked", True)),
                "attestation": _text(payload.get("attestation") or payload.get("notes"), 2000),
                "waiver_reason": _text(payload.get("waiver_reason") or payload.get("override_reason"), 1000),
            },
            blocked_keys=RIGHTS_BLOCKED_KEYS,
        )
        if review["review_mode"] != "manual":
            raise RightsClearanceError("Rights clearance review must be manual.")
        if not review["confirmed_by"]:
            raise RightsClearanceError("confirmed_by is required for rights clearance review.")
        if status == "waived" and not review["waiver_reason"]:
            raise RightsClearanceError("waiver_reason is required when rights clearance is waived.")
        record["manual_clearance"] = review
        record["updated_at"] = now
        record["source_hash"] = rights_track_source_hash(record)
        record["stale"] = False
        record["stale_reasons"] = []
        record["integrity_hash"] = rights_track_integrity_hash(record)
        clean = sanitize_metadata(record, blocked_keys=RIGHTS_BLOCKED_KEYS)
        write_json(self.track_path(release_id, track_id), clean)
        self._append_event(release_id, "rights_track_reviewed", {"track_id": track_id, "status": status}, now)
        self._mark_export_stale(release_id, "rights_review_changed")
        return clean

    def reset_track_review(self, release_id: str, track_id: str, *, reason: str, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        self._ensure_mutable(release_id)
        record = self.read_track(release_id, track_id)
        record.pop("manual_clearance", None)
        record["updated_at"] = now
        record["reset_reason"] = _text(reason, 1000)
        record["source_hash"] = rights_track_source_hash(record)
        record["integrity_hash"] = rights_track_integrity_hash(record)
        clean = sanitize_metadata(record, blocked_keys=RIGHTS_BLOCKED_KEYS)
        write_json(self.track_path(release_id, track_id), clean)
        self._append_event(release_id, "rights_track_review_reset", {"track_id": track_id, "reason": reason}, now)
        self._mark_export_stale(release_id, "rights_review_reset")
        return clean

    def refresh_report(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        release = self.release_store.get_release(release_id)
        parties = self.list_parties(release_id)
        party_map = {str(item.get("party_id") or ""): item for item in parties}
        metadata = read_release_metadata(self.release_store, release_id, default={})
        rows: list[dict[str, Any]] = []
        failures: list[str] = []
        warnings: list[str] = []
        for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
            record = self.read_track(release_id, track.track_id, default={})
            if not record:
                row = {"track_id": track.track_id, "status": "failed", "failures": ["missing_track_rights_record"], "warnings": []}
                failures.append(f"{track.track_id}:missing_track_rights_record")
                rows.append(row)
                continue
            metadata_track = _metadata_track_from_doc(metadata, track.track_id)
            current_hash = rights_track_source_hash({**record, "track_snapshot": _track_snapshot(track), "metadata_snapshot": _metadata_snapshot(metadata_track)})
            stale_reasons = []
            if str(record.get("source_hash") or "") != current_hash:
                stale_reasons.append("source_changed")
            if not rights_track_integrity_ok(record):
                stale_reasons.append("track_integrity_failed")
            track_failures, track_warnings = _evaluate_track(record, party_map=party_map, metadata_track=metadata_track)
            if stale_reasons:
                track_failures.extend(stale_reasons)
            row_status = "failed" if track_failures else "warning" if track_warnings else "passed"
            row = {
                "track_id": track.track_id,
                "disc_number": track.disc_number,
                "track_number": track.track_number,
                "title": track.title,
                "status": row_status,
                "manual_clearance_status": (record.get("manual_clearance") or {}).get("status") if isinstance(record.get("manual_clearance"), dict) else None,
                "source_hash": record.get("source_hash"),
                "rights_track_hash": record.get("integrity_hash"),
                "failures": sorted(set(track_failures)),
                "warnings": sorted(set(track_warnings)),
            }
            failures.extend(f"{track.track_id}:{item}" for item in track_failures)
            warnings.extend(f"{track.track_id}:{item}" for item in track_warnings)
            rows.append(row)
        redaction_findings = rights_redaction_findings({"parties": parties, "tracks": [self.read_track(release_id, track.track_id, default={}) for track in release.tracks]})
        failures.extend(f"redaction:{item.get('kind')}" for item in redaction_findings)
        source_hash = rights_report_source_hash(release.to_dict(), metadata, rows, parties)
        report = {
            "schema_version": RIGHTS_SCHEMA_VERSION,
            "release_id": release_id,
            "status": "failed" if failures else "warning" if warnings else "passed",
            "generated_at": now,
            "source_hash": source_hash,
            "track_count": len(release.tracks),
            "passed_track_count": sum(1 for row in rows if row.get("status") == "passed"),
            "warning_track_count": sum(1 for row in rows if row.get("status") == "warning"),
            "failed_track_count": sum(1 for row in rows if row.get("status") == "failed"),
            "manual_cleared_track_count": sum(1 for row in rows if row.get("manual_clearance_status") in {"accepted", "waived"}),
            "parties_count": len(parties),
            "tracks": rows,
            "failures": sorted(set(failures)),
            "warnings": sorted(set(warnings)),
            "redaction_findings": redaction_findings,
        }
        report["integrity_hash"] = rights_report_integrity_hash(report)
        clean = sanitize_metadata(report, blocked_keys=RIGHTS_BLOCKED_KEYS)
        write_json(self.report_path(release_id), clean)
        self._append_event(release_id, "rights_report_refreshed", {"status": clean.get("status"), "track_count": len(rows)}, now)
        return clean

    def read_report(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        self.release_store.get_release(release_id)
        path = self.report_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise RightsClearanceNotFoundError("Rights clearance report does not exist.")
        report = sanitize_metadata(read_json(path), blocked_keys=RIGHTS_BLOCKED_KEYS)
        if not rights_report_integrity_ok(report):
            report = {**report, "integrity_ok": False}
        else:
            report = {**report, "integrity_ok": True}
        current_source = self._current_report_source_hash(release_id, report)
        stale = bool(current_source and str(report.get("source_hash") or "") != current_source)
        if stale:
            report = {**report, "stale": True, "current_source_hash": current_source, "stale_reasons": ["source_changed"]}
        else:
            report = {**report, "stale": False, "stale_reasons": []}
        return sanitize_metadata(report, blocked_keys=RIGHTS_BLOCKED_KEYS)

    def gate(self, release_id: str, *, required: bool = False, now: str | None = None) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "require_rights_clearance": False, "hard_block": False}
        try:
            report = self.read_report(release_id)
        except RightsClearanceError as exc:
            return {"status": "failed", "require_rights_clearance": True, "hard_block": True, "message": str(exc), "failures": ["report_missing"]}
        failures: list[str] = []
        if report.get("status") != "passed":
            failures.append(f"report_status:{report.get('status')}")
        if report.get("stale"):
            failures.append("report_stale")
        if not report.get("integrity_ok"):
            failures.append("report_integrity")
        for row in report.get("tracks", []) if isinstance(report.get("tracks"), list) else []:
            if isinstance(row, dict) and row.get("status") != "passed":
                failures.append(f"{row.get('track_id')}:track_not_passed")
        failed = bool(failures)
        return {
            "status": "failed" if failed else "passed",
            "require_rights_clearance": True,
            "hard_block": failed,
            "message": "Rights clearance gate failed." if failed else "Rights clearance gate passed.",
            "report_hash": report.get("integrity_hash"),
            "source_hash": report.get("source_hash"),
            "track_count": report.get("track_count", 0),
            "manual_cleared_track_count": report.get("manual_cleared_track_count", 0),
            "failures": sorted(set(failures)),
        }

    def export_release(self, release_id: str, export_dir: Path) -> dict[str, Any]:
        report = self.read_report(release_id, default={})
        if not report:
            return {"status": "missing", "summary_path": None}
        root = export_dir / "rights"
        tracks_dir = root / "tracks"
        tracks_dir.mkdir(parents=True, exist_ok=True)
        exported_tracks: list[dict[str, Any]] = []
        for row in report.get("tracks", []) if isinstance(report.get("tracks"), list) else []:
            track_id = str(row.get("track_id") or "")
            if not track_id:
                continue
            record = self.read_track(release_id, track_id, default={})
            if not record:
                continue
            target_path = tracks_dir / f"{_safe_id(track_id, 'track')}.json"
            write_json(target_path, record)
            exported_tracks.append({"track_id": track_id, "path": f"rights/tracks/{target_path.name}", "payload_hash": record.get("integrity_hash")})
        write_json(root / "report.json", report)
        summary = rights_export_summary(report, exported_tracks=exported_tracks)
        write_json(root / "summary.json", summary)
        return summary

    def export_package_summary(self, release_id: str, export_dir: Path) -> dict[str, Any]:
        report = self.read_report(release_id, default={})
        if not report:
            return {"status": "missing", "summary_path": None}
        root = export_dir / "rights"
        root.mkdir(parents=True, exist_ok=True)
        summary = rights_export_summary(report, exported_tracks=[])
        write_json(root / "summary.json", summary)
        return summary

    def _ensure_mutable(self, release_id: str) -> None:
        document = self.release_store.get_release(release_id)
        if document.status == "archived":
            raise RightsClearanceStateError("Archived releases are read-only.")
        if document.status == "signed" or self.release_store.read_signoff(release_id, default={}):
            raise RightsClearanceStateError("Signed releases cannot change rights clearance evidence. Reset signoff first.")

    def _mark_export_stale(self, release_id: str, reason: str) -> None:
        document = self.release_store.get_release(release_id)
        if document.latest_export_summary:
            document.latest_export_summary = {**document.latest_export_summary, "status": "stale", "stale": True, "stale_reason": reason}
            self.release_store.save_release(document)

    def _append_event(self, release_id: str, event_type: str, payload: dict[str, Any], now: str) -> None:
        path = self.events_path(release_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now, "type": event_type, "payload": payload}, blocked_keys=RIGHTS_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.release_store.append_event(release_id, event_type, payload)

    def _current_report_source_hash(self, release_id: str, report: dict[str, Any]) -> str:
        release = self.release_store.get_release(release_id)
        parties = self.list_parties(release_id)
        metadata = read_release_metadata(self.release_store, release_id, default={})
        rows: list[dict[str, Any]] = []
        for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
            record = self.read_track(release_id, track.track_id, default={})
            metadata_track = _metadata_track_from_doc(metadata, track.track_id)
            current_hash = rights_track_source_hash({**record, "track_snapshot": _track_snapshot(track), "metadata_snapshot": _metadata_snapshot(metadata_track)}) if record else ""
            row = next((item for item in report.get("tracks", []) if isinstance(item, dict) and item.get("track_id") == track.track_id), {})
            rows.append({"track_id": track.track_id, "status": row.get("status"), "source_hash": current_hash, "rights_track_hash": record.get("integrity_hash") if record else None})
        return rights_report_source_hash(release.to_dict(), metadata, rows, parties)


def rights_track_source_hash(record: dict[str, Any]) -> str:
    return stable_hash(
        sanitize_metadata(
            {
                "release_id": record.get("release_id"),
                "track_id": record.get("track_id"),
                "track_snapshot": record.get("track_snapshot"),
                "metadata_snapshot": record.get("metadata_snapshot"),
                "contributors": record.get("contributors", []),
                "source_usages": record.get("source_usages", []),
                "instrumental": record.get("instrumental"),
                "metadata_credits_waived": record.get("metadata_credits_waived"),
                "manual_clearance": record.get("manual_clearance"),
            },
            blocked_keys=RIGHTS_BLOCKED_KEYS,
        )
    )


def rights_track_integrity_hash(record: dict[str, Any]) -> str:
    payload = {key: value for key, value in record.items() if key not in RIGHTS_TRACK_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=RIGHTS_BLOCKED_KEYS))


def rights_track_integrity_ok(record: dict[str, Any]) -> bool:
    expected = str((record or {}).get("integrity_hash") or "")
    return bool(expected) and expected == rights_track_integrity_hash(record)


def rights_report_source_hash(release: dict[str, Any], metadata: dict[str, Any], rows: list[dict[str, Any]], parties: list[dict[str, Any]]) -> str:
    return stable_hash(
        sanitize_metadata(
            {
                "release": {
                    "release_id": release.get("release_id"),
                    "name": release.get("name"),
                    "primary_artist": release.get("primary_artist"),
                    "tracks": [
                        {
                            "track_id": track.get("track_id"),
                            "disc_number": track.get("disc_number"),
                            "track_number": track.get("track_number"),
                            "title": track.get("title"),
                            "artist": track.get("artist"),
                            "project_id": track.get("project_id"),
                            "version_id": track.get("version_id"),
                        }
                        for track in release.get("tracks", [])
                        if isinstance(track, dict)
                    ],
                },
                "metadata_hash": stable_hash(metadata or {}),
                "track_rows": [{key: row.get(key) for key in ("track_id", "status", "source_hash", "rights_track_hash")} for row in rows],
                "parties_hash": stable_hash({"parties": parties}),
            },
            blocked_keys=RIGHTS_BLOCKED_KEYS,
        )
    )


def rights_report_integrity_hash(report: dict[str, Any]) -> str:
    payload = {key: value for key, value in report.items() if key not in RIGHTS_REPORT_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=RIGHTS_BLOCKED_KEYS))


def rights_report_integrity_ok(report: dict[str, Any]) -> bool:
    expected = str((report or {}).get("integrity_hash") or "")
    return bool(expected) and expected == rights_report_integrity_hash(report)


def rights_summary_hash(summary: dict[str, Any]) -> str:
    payload = {key: value for key, value in summary.items() if key not in RIGHTS_SUMMARY_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=RIGHTS_BLOCKED_KEYS))


def rights_summary_integrity_ok(summary: dict[str, Any]) -> bool:
    expected = str((summary or {}).get("summary_hash") or "")
    return bool(expected) and expected == rights_summary_hash(summary)


def rights_export_summary(report: dict[str, Any], *, exported_tracks: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "schema_version": RIGHTS_SCHEMA_VERSION,
        "status": report.get("status") or "missing",
        "summary_path": "rights/summary.json",
        "report_path": "rights/report.json",
        "report_hash": report.get("integrity_hash"),
        "source_hash": report.get("source_hash"),
        "track_count": report.get("track_count", 0),
        "manual_cleared_track_count": report.get("manual_cleared_track_count", 0),
        "failed_track_count": report.get("failed_track_count", 0),
        "warning_track_count": report.get("warning_track_count", 0),
        "tracks": exported_tracks,
    }
    summary["summary_hash"] = rights_summary_hash(summary)
    return sanitize_metadata(summary, blocked_keys=RIGHTS_BLOCKED_KEYS)


def rights_redaction_findings(value: Any, *, path: str = "rights") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in RIGHTS_BLOCKED_KEYS:
                findings.append({"path": path, "kind": "blocked_key", "key": str(key)})
            findings.extend(rights_redaction_findings(item, path=f"{path}.{key}"))
        return findings
    if isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(rights_redaction_findings(item, path=f"{path}[{index}]"))
        return findings
    if isinstance(value, str):
        for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path, "kind": "sensitive_value"})
        if _looks_like_local_path(value):
            findings.append({"path": path, "kind": "local_path_value"})
    return findings


def verify_release_rights_package_evidence(
    *,
    manifest_summary: dict[str, Any],
    summary: dict[str, Any],
    report: dict[str, Any],
    tracks: dict[str, dict[str, Any]],
    required: bool,
) -> list[str]:
    failures: list[str] = []
    if required and not manifest_summary:
        failures.append("manifest_rights_missing")
        return failures
    if not summary:
        failures.append("summary_missing")
        return failures
    if str(manifest_summary.get("summary_hash") or "") != str(summary.get("summary_hash") or ""):
        failures.append("summary_hash")
    if not rights_summary_integrity_ok(summary):
        failures.append("summary_integrity")
    if not report:
        failures.append("report_missing")
    else:
        if str(summary.get("report_hash") or "") != str(report.get("integrity_hash") or ""):
            failures.append("report_hash")
        if not rights_report_integrity_ok(report):
            failures.append("report_integrity")
        if required and report.get("status") != "passed":
            failures.append(f"report_status:{report.get('status')}")
    for row in summary.get("tracks", []) if isinstance(summary.get("tracks"), list) else []:
        if not isinstance(row, dict):
            continue
        track_id = str(row.get("track_id") or "")
        record = tracks.get(track_id)
        if not record:
            failures.append(f"{track_id}:track_record_missing")
            continue
        if str(row.get("payload_hash") or "") != str(record.get("integrity_hash") or ""):
            failures.append(f"{track_id}:track_hash")
        if not rights_track_integrity_ok(record):
            failures.append(f"{track_id}:track_integrity")
    if required and not summary.get("tracks"):
        failures.append("track_records_missing")
    if rights_redaction_findings({"summary": summary, "report": report, "tracks": list(tracks.values())}):
        failures.append("redaction")
    return sorted(set(failures))


def verify_rights_summary_evidence(*, manifest_summary: dict[str, Any], summary: dict[str, Any], required: bool) -> list[str]:
    failures: list[str] = []
    if required and not manifest_summary:
        failures.append("manifest_rights_missing")
        return failures
    if not summary:
        failures.append("summary_missing")
        return failures
    if str(manifest_summary.get("summary_hash") or "") != str(summary.get("summary_hash") or ""):
        failures.append("summary_hash")
    if not rights_summary_integrity_ok(summary):
        failures.append("summary_integrity")
    if required and summary.get("status") != "passed":
        failures.append(f"summary_status:{summary.get('status')}")
    if rights_redaction_findings(summary):
        failures.append("redaction")
    return sorted(set(failures))


def _evaluate_track(record: dict[str, Any], *, party_map: dict[str, dict[str, Any]], metadata_track: dict[str, Any]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    contributors = [item for item in _list(record.get("contributors")) if isinstance(item, dict)]
    if not contributors:
        failures.append("contributors_missing")
    for contributor in contributors:
        party_id = str(contributor.get("party_id") or "")
        if not party_id or party_id not in party_map:
            failures.append(f"party_missing:{party_id or 'missing'}")
        if not _text(contributor.get("role"), 80):
            failures.append("contributor_role_missing")
    roles = {str(item.get("role") or "").lower() for item in contributors}
    if "composer" not in roles:
        failures.append("composer_missing")
    instrumental = bool(record.get("instrumental", metadata_track.get("instrumental", False)))
    lyrics = _text(metadata_track.get("lyrics"), 200000)
    if lyrics and not instrumental and "lyricist" not in roles:
        failures.append("lyricist_missing_for_lyrics")
    for role in CONTRIBUTOR_ROLES_REQUIRING_SPLITS:
        role_rows = [item for item in contributors if str(item.get("role") or "").lower() == role]
        if not role_rows:
            continue
        total = sum(float(item.get("share") or item.get("split_percent") or 0) for item in role_rows)
        if abs(total - 100.0) > 0.01:
            failures.append(f"{role}_split_not_100")
    metadata_credits = _metadata_credit_names(metadata_track)
    if metadata_credits and not bool(record.get("metadata_credits_waived", False)):
        rights_names = {_norm_name(party_map.get(str(item.get("party_id") or ""), {}).get("public_credit_name") or party_map.get(str(item.get("party_id") or ""), {}).get("display_name")) for item in contributors}
        for role, names in metadata_credits.items():
            if role in {"composer", "lyricist"}:
                missing = sorted(name for name in names if name and name not in rights_names)
                if missing:
                    failures.append(f"metadata_credit_missing_in_rights:{role}")
    for source in _list(record.get("source_usages")):
        if not isinstance(source, dict):
            continue
        status = str(source.get("status") or "unknown").lower()
        risk = str(source.get("risk_level") or source.get("risk") or "medium").lower()
        if status in SOURCE_BLOCKING_STATUSES and risk in {"medium", "high", "critical"}:
            failures.append(f"source_uncleared:{source.get('source_id') or source.get('name') or 'source'}")
        if status not in SOURCE_SAFE_STATUSES and status not in SOURCE_BLOCKING_STATUSES:
            warnings.append(f"source_unknown_status:{status}")
    manual = record.get("manual_clearance") if isinstance(record.get("manual_clearance"), dict) else {}
    if manual.get("status") not in {"accepted", "waived"}:
        failures.append("manual_clearance_missing")
    if manual.get("review_mode") != "manual":
        failures.append("manual_clearance_not_manual")
    if not _text(manual.get("confirmed_by"), 160):
        failures.append("manual_clearance_reviewer_missing")
    if manual.get("status") == "waived" and not _text(manual.get("waiver_reason"), 1000):
        failures.append("waiver_reason_missing")
    return failures, warnings


def _normalize_contributor(item: Any) -> dict[str, Any]:
    data = item if isinstance(item, dict) else {}
    role = str(data.get("role") or "composer").strip().lower()
    share = data.get("share") if data.get("share") is not None else data.get("split_percent")
    try:
        share_value = round(float(share), 4)
    except (TypeError, ValueError):
        share_value = 0.0
    return sanitize_metadata(
        {
            "party_id": _safe_id(str(data.get("party_id") or ""), "party") if str(data.get("party_id") or "").strip() else "",
            "role": role,
            "share": share_value,
            "territory": _text(data.get("territory") or "worldwide", 120),
            "rights_type": _text(data.get("rights_type") or role, 120),
            "notes": _text(data.get("notes"), 1000),
        },
        blocked_keys=RIGHTS_BLOCKED_KEYS,
    )


def _normalize_source_usage(item: Any) -> dict[str, Any]:
    data = item if isinstance(item, dict) else {}
    return sanitize_metadata(
        {
            "source_id": _safe_id(str(data.get("source_id") or ""), "source") if str(data.get("source_id") or "").strip() else "",
            "name": _text(data.get("name") or data.get("title"), 180),
            "source_type": _text(data.get("source_type") or data.get("type") or "original", 80),
            "status": str(data.get("status") or "original").strip().lower(),
            "risk_level": str(data.get("risk_level") or data.get("risk") or "low").strip().lower(),
            "license_ref": _text(data.get("license_ref") or data.get("license"), 240),
            "notes": _text(data.get("notes"), 1000),
        },
        blocked_keys=RIGHTS_BLOCKED_KEYS,
    )


def _release_track(release: Any, track_id: str) -> Any | None:
    for track in getattr(release, "tracks", []):
        if getattr(track, "track_id", "") == track_id:
            return track
    return None


def _track_snapshot(track: Any) -> dict[str, Any]:
    return {
        "track_id": getattr(track, "track_id", None),
        "disc_number": getattr(track, "disc_number", None),
        "track_number": getattr(track, "track_number", None),
        "title": getattr(track, "title", None),
        "artist": getattr(track, "artist", None),
        "project_id": getattr(track, "project_id", None),
        "version_id": getattr(track, "version_id", None),
        "final_export_hash": getattr(track, "final_export_hash", None),
    }


def _metadata_track(release_store: ReleaseStore, release_id: str, track_id: str) -> dict[str, Any]:
    metadata = read_release_metadata(release_store, release_id, default={})
    return _metadata_track_from_doc(metadata, track_id)


def _metadata_track_from_doc(metadata: dict[str, Any], track_id: str) -> dict[str, Any]:
    for track in metadata.get("tracks", []) if isinstance(metadata.get("tracks"), list) else []:
        if isinstance(track, dict) and str(track.get("track_id") or "") == track_id:
            return track
    return {}


def _metadata_snapshot(metadata_track: dict[str, Any]) -> dict[str, Any]:
    return {
        "track_id": metadata_track.get("track_id"),
        "title": metadata_track.get("title"),
        "display_artist": metadata_track.get("display_artist"),
        "primary_artist": metadata_track.get("primary_artist"),
        "instrumental": metadata_track.get("instrumental"),
        "lyrics_hash": stable_hash({"lyrics": metadata_track.get("lyrics")}) if metadata_track.get("lyrics") else None,
        "credits": [
            {"role": credit.get("role"), "name": credit.get("name")}
            for credit in metadata_track.get("credits", [])
            if isinstance(credit, dict)
        ],
    }


def _metadata_credit_names(metadata_track: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for credit in metadata_track.get("credits", []) if isinstance(metadata_track.get("credits"), list) else []:
        if not isinstance(credit, dict):
            continue
        role = str(credit.get("role") or "").lower()
        name = _norm_name(credit.get("name"))
        if role and name:
            result.setdefault(role, set()).add(name)
    return result


def _read_json_default(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    value = read_json(path)
    return value if isinstance(value, dict) else dict(default)


def _safe_id(value: str, prefix: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip()).strip("-")
    return clean or f"{prefix}-000001"


def _next_id(rows: list[Any], prefix: str, field: str) -> str:
    used = {str(item.get(field) or "") for item in rows if isinstance(item, dict)}
    for index in range(1, 1_000_000):
        candidate = f"{prefix}-{index:06d}"
        if candidate not in used:
            return candidate
    raise RightsClearanceError("Unable to allocate rights id.")


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _norm_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=RIGHTS_BLOCKED_KEYS)


def _looks_like_local_path(value: str) -> bool:
    text = str(value)
    return bool(re.search(r"(?i)\b[A-Z]:[\\/]", text) or re.search(r"(?<!\S)/(?:Users|home)/", text) or re.search(r"\\\\[^\\/]+[\\/]", text))
