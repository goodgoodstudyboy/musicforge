# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.audio_campaign_governance import AudioCampaignGovernanceStore as AudioCampaignGovernanceStore
from song_agent.domains.quality.audio_campaign_planner import AudioCampaignPlannerStore as AudioCampaignPlannerStore
from song_agent.domains.quality.audio_campaign_remediation import AudioCampaignRemediationStore as AudioCampaignRemediationStore
from song_agent.domains.quality.audio_campaigns import AudioCampaignStore as AudioCampaignStore
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_certification import ReleaseAudioCertificationStore as ReleaseAudioCertificationStore
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package as verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_timeline_verifier import RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE as RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE, RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION as RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION, verify_release_audio_timeline_package as verify_release_audio_timeline_package, write_release_audio_timeline_verification_report as write_release_audio_timeline_verification_report
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.quality.v142_rat_readiness import ReleaseAudioTimelineStoreReadinessMixin
from song_agent.domains.quality import v142_rat_readiness as _v142_rat_readiness
from song_agent.domains.quality.v142_rat_evidence import ReleaseAudioTimelineStoreEvidenceMixin
from song_agent.domains.quality import v142_rat_evidence as _v142_rat_evidence



class ReleaseAudioTimelineError(ValueError):
    pass


class ReleaseAudioTimelineNotFoundError(ReleaseAudioTimelineError):
    pass


class ReleaseAudioTimelineStateError(ReleaseAudioTimelineError):
    pass


class ReleaseAudioTimelineValidationError(ReleaseAudioTimelineError):
    pass


class ReleaseAudioTimelineStore(ReleaseAudioTimelineStoreReadinessMixin, ReleaseAudioTimelineStoreEvidenceMixin):
    def __init__(
        self,
        *,
        release_store: ReleaseStore | None = None,
        project_store: ProjectStore | None = None,
        planner_store: AudioCampaignPlannerStore | None = None,
        campaign_store: AudioCampaignStore | None = None,
        governance_store: AudioCampaignGovernanceStore | None = None,
        remediation_store: AudioCampaignRemediationStore | None = None,
        certification_store: ReleaseAudioCertificationStore | None = None,
    ) -> None:
        self.release_store = release_store or ReleaseStore()
        self.project_store = project_store or self.release_store.project_store
        self.campaign_store = campaign_store or AudioCampaignStore()
        self.planner_store = planner_store or AudioCampaignPlannerStore(release_store=self.release_store, project_store=self.project_store, audio_campaign_store=self.campaign_store)
        self.governance_store = governance_store or AudioCampaignGovernanceStore(campaign_store=self.campaign_store)
        self.remediation_store = remediation_store or AudioCampaignRemediationStore(
            release_store=self.release_store,
            project_store=self.project_store,
            planner_store=self.planner_store,
            campaign_store=self.campaign_store,
            fix_sprint_store=self.campaign_store.audio_fix_sprint_store,
        )
        self.certification_store = certification_store or ReleaseAudioCertificationStore(
            release_store=self.release_store,
            project_store=self.project_store,
            planner_store=self.planner_store,
            campaign_store=self.campaign_store,
            governance_store=self.governance_store,
            remediation_store=self.remediation_store,
        )
        self.lock = threading.RLock()









































def _checks(track_index: ImplementationDocument, trend: ImplementationDocument, risks: ImplementationDocument, cert_binding: ImplementationDocument) -> list[ImplementationDocument]:
    summary = _as_document(track_index.get("summary"))
    track_count = int(summary.get("track_count") or 0)
    return [
        {"check_id": "release_audio_timeline_tracks_present", "status": "passed" if track_count > 0 else "failed", "message": "Release timeline has tracks."},
        {"check_id": "release_audio_timeline_manual_reviews", "status": "passed" if int(summary.get("manual_review_count") or 0) >= track_count and track_count else "failed", "message": "Timeline has manual review coverage."},
        {"check_id": "release_audio_timeline_real_audio", "status": "passed" if int(summary.get("real_audio_review_count") or 0) >= track_count and track_count else "failed", "message": "Timeline has real audio coverage."},
        {"check_id": "release_audio_timeline_certification", "status": "passed" if cert_binding.get("status") == "passed" else "failed", "message": "Timeline binds passed Release Audio Certification."},
        {"check_id": "release_audio_timeline_no_blocking_risks", "status": "passed" if int((risks.get("summary") or {}).get("blocking_risk_count") or 0) == 0 else "failed", "message": "Timeline has no blocking risks."},
        {"check_id": "release_audio_timeline_quality_trend", "status": "passed" if (trend.get("summary") or {}).get("real_audio_coverage", 0) == 1.0 else "warning", "message": "Timeline quality trend is release-ready."},
    ]


def _event(release_id: str, timeline_id: str, sequence: int, track_identity: ImplementationDocument, event_type: str, status: str, severity: str, payload: ImplementationDocument, previous_event_hash: str | None) -> ImplementationDocument:
    clean_payload = sanitize_metadata(payload)
    event = sanitize_metadata(
        {
            "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
            "event_id": f"rate-evt-{sequence:06d}",
            "release_id": release_id,
            "timeline_id": timeline_id,
            "track_identity": track_identity,
            "event_type": event_type,
            "status": status,
            "severity": severity,
            "source_component": event_type.split("_")[0],
            "source_id": track_identity.get("track_id") if isinstance(track_identity, dict) else None,
            "source_hash": stable_hash(clean_payload),
            "payload": clean_payload,
            "evidence_refs": [],
            "recorded_at": None,
            "previous_event_hash": previous_event_hash,
            "payload_hash": stable_hash(clean_payload),
        }
    )
    event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
    return event


def _derive_from_events(release_id: Any, timeline_id: Any, events: list[ImplementationDocument], *, source_hash: Any) -> ImplementationDocument:
    from song_agent.domains.quality.release_audio_timeline_verifier import _derive_from_events as derive

    return derive(release_id, timeline_id, events, source_hash=source_hash)


def _identity_key(project_id: str, version_id: str, final_export_hash: str) -> str:
    if not project_id or not version_id or not final_export_hash:
        return ""
    return stable_hash({"project_id": project_id, "version_id": version_id, "final_export_hash": final_export_hash})


def _case_identity_key(case: ImplementationDocument) -> str:
    return _identity_key(str(case.get("project_id") or ""), str(case.get("version_id") or ""), str(case.get("final_export_hash") or ""))


def _renderer_release_ready(renderer: ImplementationDocument) -> bool:
    return renderer.get("runner_kind") == "real" and renderer.get("release_ready") is not False


def _read_optional_json(path: Path) -> ImplementationDocument:
    try:
        if path.exists():
            return read_json(path)
    except (OSError, ValueError):
        return {}
    return {}


def _read_jsonl(path: Path) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    if not path.exists():
        raise ReleaseAudioTimelineNotFoundError(f"Timeline event ledger not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_jsonl(path: Path, rows: list[ImplementationDocument]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _event_ledger_hash(events: list[ImplementationDocument]) -> str:
    return stable_hash(events)


def _readme(report: ImplementationDocument, track_index: ImplementationDocument, trend: ImplementationDocument, risks: ImplementationDocument) -> str:
    summary = _as_document(report.get("summary"))
    return "\n".join(
        [
            "MusicForge Release Audio Timeline",
            f"release_id: {report.get('release_id')}",
            f"timeline_id: {report.get('timeline_id')}",
            f"status: {report.get('status')}",
            f"tracks: {summary.get('track_count')}",
            f"manual_review_count: {summary.get('manual_review_count')}",
            f"real_audio_review_count: {summary.get('real_audio_review_count')}",
            f"open_risk_count: {(risks.get('summary') or {}).get('open_risk_count')}",
            f"real_audio_coverage: {(trend.get('summary') or {}).get('real_audio_coverage')}",
            "",
            "This package contains audio certification timeline summaries only. It does not embed audio files or local workspace paths.",
            f"track_index_status: {track_index.get('summary', {}).get('certified_track_count')}",
            "",
        ]
    )


def _file_record(path: Path, root: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _semantic_hash(value: Any) -> str:
    return stable_hash(_strip_semantic_volatile(value))


def _strip_semantic_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_semantic_volatile(item) for key, item in value.items() if key not in {"generated_at", "integrity_hash"}}
    if isinstance(value, list):
        return [_strip_semantic_volatile(item) for item in value]
    return value

_v142_rat_readiness.bind_globals(globals())
_v142_rat_evidence.bind_globals(globals())
