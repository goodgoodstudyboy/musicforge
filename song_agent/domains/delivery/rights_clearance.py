# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_float as _as_float, as_list as _as_list, document_or as _document_or

import json as json
import re as re
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.assets import AssetStore as AssetStore
from song_agent.domains.studio.context_packs import ContextPackStore as ContextPackStore
from song_agent.domains.studio.library_index import asset_source_hash as asset_source_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.studio.references import ReferenceStore as ReferenceStore
from song_agent.domains.delivery.release_metadata import read_release_metadata as read_release_metadata
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash


RIGHTS_SCHEMA_VERSION = 1
RIGHTS_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}
RIGHTS_REPORT_INTEGRITY_EXCLUDE = {"integrity_hash", "integrity_ok", "stale", "stale_reasons", "current_source_hash"}
RIGHTS_TRACK_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons"}
RIGHTS_SUMMARY_INTEGRITY_EXCLUDE = {"summary_hash"}
CONTRIBUTOR_ROLES_REQUIRING_SPLITS = {"composer", "lyricist"}
SOURCE_BLOCKING_STATUSES = {"uncleared", "blocked", "unknown", "pending"}
SOURCE_SAFE_STATUSES = {"cleared", "waived", "owned", "public_domain", "original"}
SOURCE_COVERAGE_SAFE_STATUSES = SOURCE_SAFE_STATUSES - {"original"}


class RightsClearanceError(ValueError):
    pass


class RightsClearanceNotFoundError(RightsClearanceError):
    pass


class RightsClearanceStateError(RightsClearanceError):
    pass


class RightsClearanceStore:
    def __init__(
        self,
        release_store: ReleaseStore,
        *,
        asset_store: AssetStore | None = None,
        reference_store: ReferenceStore | None = None,
        context_pack_store: ContextPackStore | None = None,
    ) -> None:
        self.release_store = release_store
        base_root = release_store.root.parent
        self.asset_store = asset_store or AssetStore(base_root / "assets")
        self.reference_store = reference_store or ReferenceStore(base_root / "references")
        self.context_pack_store = context_pack_store or ContextPackStore(base_root / "context-packs")

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

    def list_parties(self, release_id: str) -> list[DomainDocument]:
        self.release_store.get_release(release_id)
        data = _read_json_default(self.parties_path(release_id), {"parties": []})
        parties = _as_list(data.get("parties"))
        return [sanitize_metadata(item, blocked_keys=RIGHTS_BLOCKED_KEYS) for item in parties if isinstance(item, dict)]

    def upsert_party(self, release_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_mutable(release_id)
        data = _read_json_default(self.parties_path(release_id), {"schema_version": RIGHTS_SCHEMA_VERSION, "release_id": release_id, "parties": []})
        parties = _as_list(data.get("parties"))
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
        next_parties: list[ImplementationDocument] = []
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

    def read_track(self, release_id: str, track_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        self.release_store.get_release(release_id)
        path = self.track_path(release_id, track_id)
        if not path.exists():
            if default is not None:
                return default
            raise RightsClearanceNotFoundError(f"Rights track record not found: {track_id}.")
        return sanitize_metadata(read_json(path), blocked_keys=RIGHTS_BLOCKED_KEYS)

    def upsert_track(self, release_id: str, track_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
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
            "required_source_usages": self._required_source_usages(track),
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

    def review_track(self, release_id: str, track_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
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
        track = _release_track(self.release_store.get_release(release_id), track_id)
        if track is not None:
            record["track_snapshot"] = _track_snapshot(track)
            record["required_source_usages"] = self._required_source_usages(track)
            metadata = _metadata_track(self.release_store, release_id, track_id)
            record["metadata_snapshot"] = _metadata_snapshot(metadata)
        record["source_hash"] = rights_track_source_hash(record)
        record["stale"] = False
        record["stale_reasons"] = []
        record["integrity_hash"] = rights_track_integrity_hash(record)
        clean = sanitize_metadata(record, blocked_keys=RIGHTS_BLOCKED_KEYS)
        write_json(self.track_path(release_id, track_id), clean)
        self._append_event(release_id, "rights_track_reviewed", {"track_id": track_id, "status": status}, now)
        self._mark_export_stale(release_id, "rights_review_changed")
        return clean

    def reset_track_review(self, release_id: str, track_id: str, *, reason: str, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_mutable(release_id)
        record = self.read_track(release_id, track_id)
        record.pop("manual_clearance", None)
        record["updated_at"] = now
        track = _release_track(self.release_store.get_release(release_id), track_id)
        if track is not None:
            record["track_snapshot"] = _track_snapshot(track)
            record["required_source_usages"] = self._required_source_usages(track)
        record["reset_reason"] = _text(reason, 1000)
        record["source_hash"] = rights_track_source_hash(record)
        record["integrity_hash"] = rights_track_integrity_hash(record)
        clean = sanitize_metadata(record, blocked_keys=RIGHTS_BLOCKED_KEYS)
        write_json(self.track_path(release_id, track_id), clean)
        self._append_event(release_id, "rights_track_review_reset", {"track_id": track_id, "reason": reason}, now)
        self._mark_export_stale(release_id, "rights_review_reset")
        return clean

    def refresh_report(self, release_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        release = self.release_store.get_release(release_id)
        parties = self.list_parties(release_id)
        party_map = {str(item.get("party_id") or ""): item for item in parties}
        metadata = read_release_metadata(self.release_store, release_id, default={})
        rows: list[ImplementationDocument] = []
        failures: list[str] = []
        warnings: list[str] = []
        for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
            record = self.read_track(release_id, track.track_id, default={})
            if not record:
                missing_row = {"track_id": track.track_id, "status": "failed", "failures": ["missing_track_rights_record"], "warnings": []}
                failures.append(f"{track.track_id}:missing_track_rights_record")
                rows.append(missing_row)
                continue
            metadata_track = _metadata_track_from_doc(metadata, track.track_id)
            required_sources = self._required_source_usages(track)
            current_hash = rights_track_source_hash({**record, "track_snapshot": _track_snapshot(track), "metadata_snapshot": _metadata_snapshot(metadata_track), "required_source_usages": required_sources})
            stale_reasons = []
            if str(record.get("source_hash") or "") != current_hash:
                stale_reasons.append("source_changed")
            if not rights_track_integrity_ok(record):
                stale_reasons.append("track_integrity_failed")
            track_failures, track_warnings = _evaluate_track({**record, "required_source_usages": required_sources}, party_map=party_map, metadata_track=metadata_track)
            if stale_reasons:
                track_failures.extend(stale_reasons)
            row_status = "failed" if track_failures else "warning" if track_warnings else "passed"
            row: ImplementationDocument = {
                "track_id": track.track_id,
                "disc_number": track.disc_number,
                "track_number": track.track_number,
                "title": track.title,
                "status": row_status,
                "manual_clearance_status": (record.get("manual_clearance") or {}).get("status") if isinstance(record.get("manual_clearance"), dict) else None,
                "source_hash": record.get("source_hash"),
                "rights_track_hash": record.get("integrity_hash"),
                "required_source_count": len(required_sources),
                "required_sources": required_sources,
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

    def read_report(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
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

    def gate(self, release_id: str, *, required: bool = False, now: str | None = None) -> DomainDocument:
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

    def export_release(self, release_id: str, export_dir: Path) -> DomainDocument:
        report = self.read_report(release_id, default={})
        if not report:
            return {"status": "missing", "summary_path": None}
        root = export_dir / "rights"
        tracks_dir = root / "tracks"
        tracks_dir.mkdir(parents=True, exist_ok=True)
        exported_tracks: list[ImplementationDocument] = []
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

    def export_package_summary(self, release_id: str, export_dir: Path) -> DomainDocument:
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

    def _append_event(self, release_id: str, event_type: str, payload: ImplementationDocument, now: str) -> None:
        path = self.events_path(release_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now, "type": event_type, "payload": payload}, blocked_keys=RIGHTS_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.release_store.append_event(release_id, event_type, payload)

    def _current_report_source_hash(self, release_id: str, report: ImplementationDocument) -> str:
        release = self.release_store.get_release(release_id)
        parties = self.list_parties(release_id)
        metadata = read_release_metadata(self.release_store, release_id, default={})
        rows: list[ImplementationDocument] = []
        for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
            record = self.read_track(release_id, track.track_id, default={})
            metadata_track = _metadata_track_from_doc(metadata, track.track_id)
            required_sources = self._required_source_usages(track)
            current_hash = rights_track_source_hash({**record, "track_snapshot": _track_snapshot(track), "metadata_snapshot": _metadata_snapshot(metadata_track), "required_source_usages": required_sources}) if record else ""
            row = next((item for item in report.get("tracks", []) if isinstance(item, dict) and item.get("track_id") == track.track_id), {})
            rows.append({"track_id": track.track_id, "status": row.get("status"), "source_hash": current_hash, "rights_track_hash": record.get("integrity_hash") if record else None})
        return rights_report_source_hash(release.to_dict(), metadata, rows, parties)

    def _required_source_usages(self, track: Any) -> list[ImplementationDocument]:
        return required_source_usages_for_track(
            track,
            release_store=self.release_store,
            asset_store=self.asset_store,
            reference_store=self.reference_store,
            context_pack_store=self.context_pack_store,
        )


def rights_track_source_hash(record: DomainDocument) -> str:
    return stable_hash(
        sanitize_metadata(
            {
                "release_id": record.get("release_id"),
                "track_id": record.get("track_id"),
                "track_snapshot": record.get("track_snapshot"),
                "metadata_snapshot": record.get("metadata_snapshot"),
                "contributors": record.get("contributors", []),
                "source_usages": record.get("source_usages", []),
                "required_source_usages": record.get("required_source_usages", []),
                "instrumental": record.get("instrumental"),
                "metadata_credits_waived": record.get("metadata_credits_waived"),
                "manual_clearance": record.get("manual_clearance"),
            },
            blocked_keys=RIGHTS_BLOCKED_KEYS,
        )
    )


def rights_track_integrity_hash(record: DomainDocument) -> str:
    payload = {key: value for key, value in record.items() if key not in RIGHTS_TRACK_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=RIGHTS_BLOCKED_KEYS))


def rights_track_integrity_ok(record: DomainDocument) -> bool:
    expected = str((record or {}).get("integrity_hash") or "")
    return bool(expected) and expected == rights_track_integrity_hash(record)


from song_agent.domains.delivery import v142_rc_readiness as _v142_rc_readiness
from song_agent.domains.delivery.v142_rc_readiness import (
    rights_report_source_hash,
    rights_report_integrity_hash,
    rights_report_integrity_ok,
    rights_summary_hash,
    rights_summary_integrity_ok,
    rights_export_summary,
    rights_redaction_findings,
    verify_release_rights_package_evidence,
    verify_rights_summary_evidence,
    required_source_usages_for_track,
    _evaluate_track,
    _declared_source_coverage,
    _source_coverage_key,
    _project_export_snapshot,
    _final_export_manifest,
    _project_version,
    _asset_required_source,
    _reference_required_source,
)
from song_agent.domains.delivery import v142_rc_evidence as _v142_rc_evidence
from song_agent.domains.delivery.v142_rc_evidence import (
    _context_pack_required_source,
    _metadata_required_source,
    _metadata_source_id,
    _normalize_required_source,
    _used_by_version,
    _normalize_contributor,
    _normalize_source_usage,
    _release_track,
    _track_snapshot,
    _metadata_track,
    _metadata_track_from_doc,
    _metadata_snapshot,
    _metadata_credit_names,
    _read_json_default,
    _safe_id,
    _next_id,
    _text,
    _norm_name,
    _list,
    _safe_dict,
    _looks_like_local_path,
)

_v142_rc_readiness.bind_globals(globals())
_v142_rc_evidence.bind_globals(globals())
