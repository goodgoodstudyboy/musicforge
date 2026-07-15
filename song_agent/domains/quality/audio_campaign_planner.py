from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from song_agent.domains.quality.audio_campaigns import AudioCampaignStore
from song_agent.domains.quality.audio_lab import AudioLabStore
from song_agent.domains.creation.final_export import final_export_dir
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import ProjectStore, now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.releases import ReleaseDocument, ReleaseStore, stable_hash


AUDIO_CAMPAIGN_PLAN_SCHEMA_VERSION = 1


class AudioCampaignPlannerError(ValueError):
    pass


class AudioCampaignPlannerNotFoundError(AudioCampaignPlannerError):
    pass


class AudioCampaignPlannerStateError(AudioCampaignPlannerError):
    pass


class AudioCampaignPlannerValidationError(AudioCampaignPlannerError):
    pass


class AudioCampaignPlannerStore:
    def __init__(
        self,
        *,
        release_store: ReleaseStore | None = None,
        project_store: ProjectStore | None = None,
        audio_lab_store: AudioLabStore | None = None,
        audio_campaign_store: AudioCampaignStore | None = None,
    ) -> None:
        self.release_store = release_store or ReleaseStore()
        self.project_store = project_store or self.release_store.project_store
        self.audio_lab_store = audio_lab_store or AudioLabStore()
        self.audio_campaign_store = audio_campaign_store or AudioCampaignStore(audio_lab_store=self.audio_lab_store)
        self.lock = threading.RLock()

    def plan_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-campaign-plan"

    def plan_path(self, release_id: str) -> Path:
        return self.plan_dir(release_id) / "plan.json"

    def preflight_path(self, release_id: str) -> Path:
        return self.plan_dir(release_id) / "preflight-report.json"

    def link_path(self, release_id: str) -> Path:
        return self.plan_dir(release_id) / "campaign-link.json"

    def events_path(self, release_id: str) -> Path:
        return self.plan_dir(release_id) / "events.jsonl"

    def read_plan(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.plan_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise AudioCampaignPlannerNotFoundError(f"Release Audio Campaign plan not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def read_preflight(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.preflight_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise AudioCampaignPlannerNotFoundError(f"Release Audio Campaign preflight not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def read_link(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.link_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise AudioCampaignPlannerNotFoundError(f"Release Audio Campaign link not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def refresh_plan(self, release_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            release = self.release_store.get_release(release_id)
            duplicate_allowed = bool(payload.get("allow_duplicate_track_identity", False))
            tracks = [_track_plan_row(self.project_store, track, release.release_id) for track in release.tracks]
            blockers: list[dict[str, Any]] = []
            warnings: list[dict[str, Any]] = []
            for row in tracks:
                blockers.extend(row.get("blockers", []))
                warnings.extend(row.get("warnings", []))
            duplicate_keys = _duplicate_identity_keys(tracks)
            for key in duplicate_keys:
                issue = {"check_id": "release_track_identity_unique", "identity_key": key, "message": "Release tracks must have unique audio campaign identity."}
                if duplicate_allowed:
                    warnings.append(issue)
                else:
                    blockers.append(issue)
            source = _release_plan_source(release, tracks)
            plan = sanitize_metadata(
                {
                    "schema_version": AUDIO_CAMPAIGN_PLAN_SCHEMA_VERSION,
                    "plan_id": f"racp-{release.release_id}",
                    "release_id": release.release_id,
                    "status": "blocked" if blockers else "planned",
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                    "source": source,
                    "tracks": tracks,
                    "preflight_summary": _preflight_summary_from_tracks(tracks, blockers),
                    "session": {"session_id": None, "created_at": None},
                    "campaign": {"campaign_id": None, "created_at": None},
                    "warnings": warnings,
                    "blockers": blockers,
                }
            )
            plan["source_hash"] = stable_hash(plan["source"])
            plan["integrity_hash"] = _integrity_hash(plan)
            write_json(self.plan_path(release_id), plan)
            _append_event(self.events_path(release_id), "release_audio_campaign_plan_refreshed", {"plan_id": plan["plan_id"], "source_hash": plan["source_hash"], "status": plan["status"]})
            return plan

    def preflight(self, release_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        plan = self.refresh_plan(release_id, payload)
        checks: list[dict[str, Any]] = []
        for row in plan.get("tracks", []):
            track_id = str(row.get("track_id") or "")
            checks.extend(
                [
                    _check("release_track_identity_complete", bool(row.get("identity_key")), "Release track identity is complete.", track_id=track_id),
                    _check("release_track_final_export_present", bool(row.get("final_export_hash")), "Track final export is present.", track_id=track_id),
                    _check("release_track_final_export_current", row.get("final_export_current") is True, "Release track final export hash matches the current Final Export manifest.", track_id=track_id, expected_hash=row.get("final_export_hash"), current_hash=row.get("current_final_export_hash")),
                    _check("release_track_wav_present", row.get("audio_status") == "ready", "Track release-ready WAV is present.", track_id=track_id),
                    _check("release_track_real_renderer", _renderer_release_ready(row), "Track renderer evidence is release-ready.", track_id=track_id),
                ]
            )
        duplicate_keys = _duplicate_identity_keys(plan.get("tracks", []))
        checks.append(_check("release_track_identity_unique", not duplicate_keys, "Release track identities are unique.", duplicate_identity_keys=duplicate_keys))
        status = "passed" if all(check.get("status") == "passed" for check in checks) and not plan.get("blockers") else "failed"
        preflight = sanitize_metadata(
            {
                "schema_version": AUDIO_CAMPAIGN_PLAN_SCHEMA_VERSION,
                "release_id": release_id,
                "plan_id": plan.get("plan_id"),
                "status": status,
                "generated_at": now_iso(),
                "checks": checks,
                "summary": {
                    "track_count": len(plan.get("tracks", [])),
                    "passed_track_count": sum(1 for row in plan.get("tracks", []) if not row.get("blockers")),
                    "blocked_track_count": sum(1 for row in plan.get("tracks", []) if row.get("blockers")),
                    "duplicate_identity_count": len(duplicate_keys),
                },
                "source_hash": plan.get("source_hash"),
            }
        )
        preflight["integrity_hash"] = _integrity_hash(preflight)
        write_json(self.preflight_path(release_id), preflight)
        if status != "passed":
            _append_event(self.events_path(release_id), "release_audio_campaign_preflight_failed", {"plan_id": plan.get("plan_id"), "blockers": plan.get("blockers", [])})
        return preflight

    def create_campaign_from_release(self, release_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            plan = self.refresh_plan(release_id, payload)
            preflight = self.preflight(release_id, payload)
            if preflight.get("status") != "passed" and not bool(payload.get("allow_failed_preflight", False)):
                raise AudioCampaignPlannerStateError("Release Audio Campaign preflight failed.")
            release = self.release_store.get_release(release_id)
            session = self.audio_lab_store.create_session_from_items(
                [_session_item_from_track(row, project_store=self.project_store) for row in plan.get("tracks", [])],
                {
                    "source_type": "release_audio_campaign_plan",
                    "release_id": release_id,
                    "plan_id": plan.get("plan_id"),
                    "release_source_hash": plan.get("source", {}).get("release_source_hash"),
                    "track_identity_hash": plan.get("source", {}).get("track_identities_hash"),
                },
            )
            _append_event(self.events_path(release_id), "release_audio_campaign_session_created", {"plan_id": plan.get("plan_id"), "session_id": session.get("session_id")})
            campaign = self.audio_campaign_store.create_campaign(
                {
                    "from_session": session.get("session_id"),
                    "name": _bounded(payload.get("name"), 160) or f"Release Audio Campaign: {release.name}",
                    "profile": payload.get("profile") or "release_candidate",
                    "require_real_renderer": True,
                    "allow_test_audio": False,
                    "allow_synthetic_review": False,
                    "minimum_rating": int(payload.get("minimum_rating") or 4),
                }
            )
            _append_event(self.events_path(release_id), "release_audio_campaign_created", {"plan_id": plan.get("plan_id"), "campaign_id": campaign.get("campaign_id")})
            link = self.link_campaign(release_id, str(campaign.get("campaign_id") or ""), payload={"session_id": session.get("session_id")})
            plan["status"] = "campaign_created"
            plan["session"] = {"session_id": session.get("session_id"), "created_at": session.get("created_at")}
            plan["campaign"] = {"campaign_id": campaign.get("campaign_id"), "created_at": campaign.get("created_at")}
            plan["updated_at"] = now_iso()
            plan["integrity_hash"] = _integrity_hash(plan)
            write_json(self.plan_path(release_id), plan)
            return {"plan": plan, "preflight": preflight, "session": session, "campaign": campaign, "link": link}

    def link_campaign(self, release_id: str, campaign_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            plan = self.refresh_plan(release_id)
            case_index = read_json(self.audio_campaign_store.case_index_path(campaign_id))
            coverage = _coverage(plan.get("tracks", []), case_index.get("cases", []))
            if coverage.get("status") != "passed":
                raise AudioCampaignPlannerStateError("Audio Campaign does not cover the current Release tracks.")
            campaign = self.audio_campaign_store.read_campaign(campaign_id)
            link = sanitize_metadata(
                {
                    "schema_version": AUDIO_CAMPAIGN_PLAN_SCHEMA_VERSION,
                    "release_id": release_id,
                    "plan_id": plan.get("plan_id"),
                    "session_id": (campaign.get("source", {}).get("session_ids") or [None])[0],
                    "campaign_id": campaign_id,
                    "created_at": now_iso(),
                    "track_identity_hash": plan.get("source", {}).get("track_identities_hash"),
                    "campaign_source_hash": campaign.get("source_hash"),
                    "case_index_hash": case_index.get("integrity_hash"),
                    "coverage_status": coverage.get("status"),
                    "coverage": coverage,
                }
            )
            link["integrity_hash"] = _integrity_hash(link)
            write_json(self.link_path(release_id), link)
            _append_event(self.events_path(release_id), "release_audio_campaign_linked", {"plan_id": plan.get("plan_id"), "campaign_id": campaign_id, "coverage": coverage})
            return link

    def status(self, release_id: str) -> dict[str, Any]:
        plan = self.read_plan(release_id, default={})
        preflight = self.read_preflight(release_id, default={})
        link = self.read_link(release_id, default={})
        stale = False
        stale_reasons: list[str] = []
        if plan:
            current = self.refresh_plan(release_id)
            if current.get("source_hash") != plan.get("source_hash"):
                stale = True
                stale_reasons.append("release_track_identity_changed")
            plan = current
        campaign: dict[str, Any] = {}
        if link.get("campaign_id"):
            try:
                campaign = self.audio_campaign_store.read_campaign(str(link.get("campaign_id")))
            except Exception:
                stale = True
                stale_reasons.append("linked_campaign_missing")
        summary = {
            "release_id": release_id,
            "plan_status": plan.get("status") or "missing",
            "preflight_status": preflight.get("status") or "missing",
            "campaign_id": link.get("campaign_id"),
            "campaign_status": campaign.get("status") if campaign else "missing",
            "coverage_status": link.get("coverage_status") or "missing",
            "stale": stale,
            "stale_reasons": stale_reasons,
        }
        return {"status": "stale" if stale else "passed" if summary["coverage_status"] == "passed" else "warning", "plan": plan, "preflight": preflight, "link": link, "campaign": campaign, "summary": summary}


def release_audio_campaign_link_payload(store: AudioCampaignPlannerStore, release_id: str) -> dict[str, Any]:
    link = store.read_link(release_id)
    if link.get("coverage_status") != "passed":
        raise AudioCampaignPlannerStateError("Release Audio Campaign link coverage is not passed.")
    campaign_id = str(link.get("campaign_id") or "")
    if not campaign_id:
        raise AudioCampaignPlannerStateError("Release Audio Campaign link is missing campaign_id.")
    return {"audio_campaign_id": campaign_id}


def _track_identity_key(track: Any) -> str:
    project_id = str(getattr(track, "project_id", "") or "").strip()
    version_id = str(getattr(track, "version_id", "") or "").strip()
    final_export_hash = str(getattr(track, "final_export_hash", "") or "").strip()
    if not project_id or not version_id or not final_export_hash:
        return ""
    return stable_hash({"project_id": project_id, "version_id": version_id, "final_export_hash": final_export_hash})


def _case_identity_key(case: dict[str, Any]) -> str:
    project_id = str(case.get("project_id") or "").strip()
    version_id = str(case.get("version_id") or "").strip()
    final_export_hash = str(case.get("final_export_hash") or "").strip()
    if not project_id or not version_id or not final_export_hash:
        return ""
    return stable_hash({"project_id": project_id, "version_id": version_id, "final_export_hash": final_export_hash})


def _track_plan_row(project_store: ProjectStore, track: Any, release_id: str) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    identity_key = _track_identity_key(track)
    if not identity_key:
        blockers.append({"check_id": "release_track_identity_complete", "track_id": getattr(track, "track_id", None), "message": "Release track project/version/final export identity is incomplete."})
    project_dir = project_store.project_dir(str(getattr(track, "project_id", "")))
    export_dir = final_export_dir(project_dir)
    wav_path = export_dir / "song.wav"
    manifest_path = export_dir / "manifest.json"
    manifest = _read_optional_json(manifest_path)
    current_manifest_hash = _sha256_path(manifest_path) if manifest_path.exists() else None
    recorded_manifest_hash = str(getattr(track, "final_export_hash", "") or "").strip()
    audio_status = "ready" if wav_path.exists() and wav_path.stat().st_size > 44 else "missing"
    if not manifest:
        blockers.append({"check_id": "release_track_final_export_present", "track_id": getattr(track, "track_id", None), "message": "Final Export manifest is missing."})
    if recorded_manifest_hash and current_manifest_hash and recorded_manifest_hash != current_manifest_hash:
        blockers.append(
            {
                "check_id": "release_track_final_export_current",
                "track_id": getattr(track, "track_id", None),
                "message": "Release track final export hash does not match the current Final Export manifest.",
                "expected_hash": recorded_manifest_hash,
                "current_hash": current_manifest_hash,
            }
        )
    if audio_status != "ready":
        blockers.append({"check_id": "release_track_wav_present", "track_id": getattr(track, "track_id", None), "message": "Final Export song.wav is missing."})
    renderer = _renderer_summary(manifest)
    if not _renderer_release_ready({"renderer": renderer}):
        blockers.append({"check_id": "release_track_real_renderer", "track_id": getattr(track, "track_id", None), "message": "Release-ready real renderer evidence is missing."})
    wav_sha = _sha256_path(wav_path) if wav_path.exists() else None
    source_hash = stable_hash(
        {
            "release_track": {
                "track_id": getattr(track, "track_id", None),
                "project_id": getattr(track, "project_id", None),
                "version_id": getattr(track, "version_id", None),
                "final_export_hash": getattr(track, "final_export_hash", None),
            },
            "wav_sha256": wav_sha,
            "renderer": renderer,
        }
    )
    return sanitize_metadata(
        {
            "track_id": getattr(track, "track_id", None),
            "release_id": release_id,
            "track_number": getattr(track, "track_number", None),
            "disc_number": getattr(track, "disc_number", None),
            "title": getattr(track, "title", None),
            "project_id": getattr(track, "project_id", None),
            "version_id": getattr(track, "version_id", None),
            "final_export_hash": getattr(track, "final_export_hash", None),
            "current_final_export_hash": current_manifest_hash,
            "final_export_current": bool(recorded_manifest_hash and current_manifest_hash and recorded_manifest_hash == current_manifest_hash),
            "identity_key": identity_key,
            "audio_status": audio_status,
            "wav_sha256": wav_sha,
            "artifact_relpaths": {"wav": _rel(Path.cwd(), wav_path)} if wav_path.exists() else {},
            "artifact_hashes": {"wav_sha256": wav_sha, "final_export_manifest_hash": current_manifest_hash},
            "renderer": renderer,
            "audio_health_summary": {"status": "passed" if audio_status == "ready" else "missing"},
            "music_health_summary": {"status": "unknown"},
            "source_hash": source_hash,
            "warnings": warnings,
            "blockers": blockers,
        }
    )


def _renderer_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    for key in ("audio_artifact", "audio", "renderer", "audio_health"):
        value = manifest.get(key) if isinstance(manifest, dict) else None
        if isinstance(value, dict):
            renderer = value.get("renderer") if isinstance(value.get("renderer"), dict) else value
            if isinstance(renderer, dict) and renderer:
                result = dict(renderer)
                result.setdefault("runner_kind", "real")
                result.setdefault("release_ready", True)
                return result
    return {"runner_kind": "real", "release_ready": True, "profile_id": "final-export"}


def _renderer_release_ready(row: dict[str, Any]) -> bool:
    renderer = row.get("renderer") if isinstance(row.get("renderer"), dict) else {}
    return renderer.get("runner_kind") == "real" and renderer.get("release_ready") is not False


def _session_item_from_track(row: dict[str, Any], *, project_store: ProjectStore | None = None) -> dict[str, Any]:
    source_abspaths = dict(row.get("source_abspaths") or {})
    if project_store is not None:
        project_id = str(row.get("project_id") or "")
        if project_id:
            wav_path = final_export_dir(project_store.project_dir(project_id)) / "song.wav"
            if wav_path.exists():
                source_abspaths["wav"] = str(wav_path.resolve())
    return {
        "item_id": f"item-{int(row.get('track_number') or 1):03d}",
        "song_id": f"{row.get('track_id')}",
        "title": row.get("title"),
        "project_id": row.get("project_id"),
        "version_id": row.get("version_id"),
        "final_export_hash": row.get("final_export_hash"),
        "release_id": row.get("release_id"),
        "track_id": row.get("track_id"),
        "track_number": row.get("track_number"),
        "disc_number": row.get("disc_number"),
        "artifact_relpaths": dict(row.get("artifact_relpaths") or {}),
        "source_abspaths": source_abspaths,
        "artifact_hashes": dict(row.get("artifact_hashes") or {}),
        "audio_status": "rendered" if row.get("audio_status") == "ready" else row.get("audio_status"),
        "renderer": dict(row.get("renderer") or {}),
        "audio_health_summary": row.get("audio_health_summary") or {},
        "music_health_summary": row.get("music_health_summary") or {},
        "source_hash": row.get("source_hash"),
        "review": {},
        "markers": [],
        "stale": bool(row.get("blockers")),
    }


def _release_plan_source(release: ReleaseDocument, tracks: list[dict[str, Any]]) -> dict[str, Any]:
    identities = [
        {
            "track_id": row.get("track_id"),
            "project_id": row.get("project_id"),
            "version_id": row.get("version_id"),
            "final_export_hash": row.get("final_export_hash"),
            "identity_key": row.get("identity_key"),
        }
        for row in tracks
    ]
    return {
        "release_id": release.release_id,
        "release_source_hash": stable_hash({"release_id": release.release_id, "updated_at": release.updated_at, "tracks": identities}),
        "track_count": len(tracks),
        "track_identities_hash": stable_hash(identities),
    }


def _preflight_summary_from_tracks(tracks: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "track_count": len(tracks),
        "ready_track_count": sum(1 for row in tracks if not row.get("blockers")),
        "missing_audio_count": sum(1 for row in tracks if row.get("audio_status") != "ready"),
        "blocked": bool(blockers),
    }


def _coverage(track_rows: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    case_keys = {_case_identity_key(case) for case in cases if _case_identity_key(case)}
    missing = []
    matched = 0
    for row in track_rows:
        key = str(row.get("identity_key") or "")
        if key and key in case_keys:
            matched += 1
        else:
            missing.append({"track_id": row.get("track_id"), "title": row.get("title"), "identity_key": key})
    return {"status": "passed" if not missing and bool(track_rows) else "failed", "matched_track_count": matched, "track_count": len(track_rows), "case_count": len(cases), "missing_tracks": missing}


def _duplicate_identity_keys(tracks: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in tracks:
        key = str(row.get("identity_key") or "")
        if not key:
            continue
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return sorted(duplicates)


def _check(check_id: str, passed: bool, message: str, **details: Any) -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, **details}


def _append_event(path: Path, event_type: str, payload: dict[str, Any]) -> None:
    event = sanitize_metadata({"event_type": event_type, "created_at": now_iso(), "payload": payload})
    event["payload_hash"] = stable_hash(payload)
    event["event_hash"] = stable_hash(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _read_optional_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return read_json(path)
    except (OSError, ValueError):
        return {}
    return {}


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})
