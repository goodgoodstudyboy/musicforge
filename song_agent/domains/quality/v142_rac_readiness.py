# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.quality.audio_campaign_governance import AudioCampaignGovernanceStore as AudioCampaignGovernanceStore
from song_agent.domains.quality.audio_campaign_planner import AudioCampaignPlannerStore as AudioCampaignPlannerStore
from song_agent.domains.quality.audio_campaign_remediation import AudioCampaignRemediationStore as AudioCampaignRemediationStore
from song_agent.domains.quality.audio_campaigns import AudioCampaignStore as AudioCampaignStore
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_certification_verifier import RELEASE_AUDIO_CERTIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_CERTIFICATION_PACKAGE_TYPE, RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION as RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION, verify_release_audio_certification_package as verify_release_audio_certification_package, write_release_audio_certification_verification_report as write_release_audio_certification_verification_report
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global item
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)






def _build_track_matrix(release_id: str, campaign_id: str, track_rows: list[DomainDocument], campaign: DomainDocument, campaign_report: DomainDocument, case_index: DomainDocument) -> DomainDocument:
    case_by_key = {_case_identity_key(case): case for case in case_index.get("cases", []) if isinstance(case, dict) and _case_identity_key(case)}
    campaign_cases = _as_list(campaign.get("cases"))
    campaign_by_key = {_case_identity_key(case): case for case in campaign_cases if isinstance(case, dict) and _case_identity_key(case)}
    report_cases = _as_list(campaign_report.get("cases"))
    report_by_case_id = {str(case.get("case_id") or ""): case for case in report_cases if isinstance(case, dict)}
    tracks: list[DomainDocument] = []
    blockers: list[DomainDocument] = []
    for row in track_rows:
        key = str(row.get("identity_key") or "")
        case = campaign_by_key.get(key) or case_by_key.get(key) or {}
        case_id = str(case.get("case_id") or "")
        report_case = report_by_case_id.get(case_id, {})
        review = _as_document(case.get("review"))
        renderer = _document_or(case.get("renderer"), row.get("renderer", {}))
        artifact_hashes = _as_document(case.get("artifact_hashes"))
        manual_accepted = review.get("status") == "accepted" and review.get("review_mode") == "manual" and review.get("playback_confirmed") is True
        wav_matches = bool(row.get("wav_sha256") and row.get("wav_sha256") == artifact_hashes.get("wav_sha256"))
        track_blockers = [dict(item) for item in row.get("blockers", []) if isinstance(item, dict)]
        if not case:
            track_blockers.append(_blocker("audio_campaign_case_missing", "Audio Campaign case is missing for this release track.", track_id=row.get("track_id")))
        if case and not manual_accepted:
            track_blockers.append(_blocker("audio_campaign_manual_review_missing", "Track is missing manual accepted playback-confirmed review.", track_id=row.get("track_id"), case_id=case_id))
        if case and not _renderer_release_ready(renderer):
            track_blockers.append(_blocker("audio_campaign_real_audio_missing", "Track campaign case is not release-ready real audio.", track_id=row.get("track_id"), case_id=case_id, renderer=renderer))
        if case and not wav_matches:
            track_blockers.append(_blocker("audio_campaign_wav_hash_mismatch", "Track campaign WAV hash does not match current Release WAV.", track_id=row.get("track_id"), case_id=case_id))
        if report_case.get("status") == "blocked":
            track_blockers.extend(_blocker(str(item), _blocker_message(str(item)), track_id=row.get("track_id"), case_id=case_id) for item in report_case.get("blockers", []) if isinstance(item, str))
        track_status = "passed" if not track_blockers else "failed"
        blockers.extend(track_blockers)
        tracks.append(
            sanitize_metadata(
                {
                    **row,
                    "case_id": case_id or None,
                    "case_source_hash": case.get("source_hash"),
                    "case_wav_sha256": artifact_hashes.get("wav_sha256"),
                    "manual_accepted": manual_accepted,
                    "review_status": review.get("status"),
                    "review_mode": review.get("review_mode"),
                    "playback_confirmed": review.get("playback_confirmed"),
                    "case_real_audio": _renderer_release_ready(renderer),
                    "wav_hash_matches_release": wav_matches,
                    "fix_sprint_id": case.get("fix", {}).get("fix_sprint_id") if isinstance(case.get("fix"), dict) else None,
                    "status": track_status,
                    "blockers": track_blockers,
                }
            )
        )
    summary = {
        "track_count": len(tracks),
        "passed_track_count": sum(1 for row in tracks if row.get("status") == "passed"),
        "manual_accepted_track_count": sum(1 for row in tracks if row.get("manual_accepted") is True),
        "real_audio_track_count": sum(1 for row in tracks if row.get("real_audio") is True and row.get("case_real_audio") is True),
        "test_fake_track_count": sum(1 for row in tracks if row.get("test_fake") is True or row.get("case_real_audio") is not True),
        "wav_hash_match_count": sum(1 for row in tracks if row.get("wav_hash_matches_release") is True),
        "failed_track_count": sum(1 for row in tracks if row.get("status") != "passed"),
    }
    matrix = sanitize_metadata({"schema_version": RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION, "release_id": release_id, "campaign_id": campaign_id or None, "generated_at": now_iso(), "status": "passed" if not blockers else "failed", "summary": summary, "tracks": tracks, "blockers": blockers})
    return matrix

def _build_evidence_index(release_id: str, campaign_id: str, source: DomainDocument, rows: list[DomainDocument], remediation_needed: bool, remediation_gate: DomainDocument, governance_gate: DomainDocument) -> DomainDocument:
    summary = {
        "evidence_count": len(rows),
        "campaign_id": campaign_id or None,
        "governance": {"status": governance_gate.get("status"), "archive_zip_sha256": governance_gate.get("archive_zip_sha256"), "verification_hash": governance_gate.get("archive_verification_hash")},
        "remediation": {"needed": remediation_needed, "status": remediation_gate.get("status"), "message": remediation_gate.get("message")},
    }
    evidence = sanitize_metadata({"schema_version": RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION, "release_id": release_id, "campaign_id": campaign_id or None, "generated_at": now_iso(), "source_hash": source.get("source_hash"), "summary": summary, "evidence": rows})
    evidence["integrity_hash"] = _integrity_hash(evidence)
    return evidence

def _build_blocker_register(release_id: str, campaign_id: str, source: DomainDocument, blockers: list[DomainDocument], warnings: list[DomainDocument]) -> DomainDocument:
    register = sanitize_metadata({"schema_version": RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION, "release_id": release_id, "campaign_id": campaign_id or None, "generated_at": now_iso(), "source_hash": source.get("source_hash"), "status": "passed" if not blockers else "failed", "summary": {"blocker_count": len(blockers), "warning_count": len(warnings)}, "blockers": blockers, "warnings": warnings})
    register["integrity_hash"] = _integrity_hash(register)
    return register

def _checks_from_matrix_and_evidence(matrix: DomainDocument, evidence: DomainDocument, blockers: DomainDocument) -> list[DomainDocument]:
    summary = _as_document(matrix.get("summary"))
    track_count = int(summary.get("track_count") or 0)
    evidence_summary = _as_document(evidence.get("summary"))
    remediation = _as_document(evidence_summary.get("remediation"))
    governance = _as_document(evidence_summary.get("governance"))
    return [
        _check("release_audio_certification_tracks_present", track_count > 0, "Release has tracks."),
        _check("release_audio_certification_track_matrix_passed", matrix.get("status") == "passed", "Track audio matrix is passed."),
        _check("release_audio_certification_manual_reviews", int(summary.get("manual_accepted_track_count") or 0) == track_count and track_count > 0, "Every track has manual accepted listening review."),
        _check("release_audio_certification_real_audio", int(summary.get("real_audio_track_count") or 0) == track_count and track_count > 0, "Every track uses release-ready real audio."),
        _check("release_audio_certification_wav_hashes", int(summary.get("wav_hash_match_count") or 0) == track_count and track_count > 0, "Campaign WAV hashes match release WAV hashes."),
        _check("release_audio_certification_campaign_governance", governance.get("status") == "passed", "Audio Campaign governance evidence is passed."),
        _check("release_audio_certification_remediation", (not remediation.get("needed")) or remediation.get("status") == "passed", "Remediation evidence is passed when needed."),
        _check("release_audio_certification_no_blockers", int(blockers.get("summary", {}).get("blocker_count") or 0) == 0, "Certification has no blockers."),
    ]

def _coverage(track_rows: list[DomainDocument], cases: list[DomainDocument]) -> DomainDocument:
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

def _remediation_needed(matrix: DomainDocument, campaign_report: DomainDocument) -> bool:
    summary = _as_document(campaign_report.get("summary"))
    return any(
        int(summary.get(key) or 0) > 0
        for key in ("needs_fix_count", "rejected_count", "open_high_marker_count", "open_critical_marker_count", "failed_fix_sprint_count", "open_fix_sprint_count")
    ) or matrix.get("status") != "passed"

def _track_blockers(track_rows: list[DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for row in track_rows:
        rows.extend([dict(item) for item in row.get("blockers", []) if isinstance(item, dict)])
    return rows

def _track_source(row: DomainDocument) -> DomainDocument:
    return {
        "track_id": row.get("track_id"),
        "project_id": row.get("project_id"),
        "version_id": row.get("version_id"),
        "final_export_hash": row.get("final_export_hash"),
        "current_final_export_hash": row.get("current_final_export_hash"),
        "wav_sha256": row.get("wav_sha256"),
        "renderer": row.get("renderer"),
    }

def _evidence(evidence_id: str, kind: str, component_id: str, status: object, integrity_hash: object, details: DomainDocument | None = None) -> DomainDocument:
    return sanitize_metadata({"evidence_id": evidence_id, "kind": kind, "component_id": component_id, "status": status, "integrity_hash": integrity_hash, "details": details or {}})

def _blocker(check_id: str, message: str, **details: object) -> DomainDocument:
    return sanitize_metadata({"check_id": check_id, "message": message, **details})

def _check(check_id: str, passed: bool, message: str) -> DomainDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message}

def _identity_key(project_id: str, version_id: str, final_export_hash: str) -> str:
    if not project_id or not version_id or not final_export_hash:
        return ""
    return stable_hash({"project_id": project_id, "version_id": version_id, "final_export_hash": final_export_hash})

def _case_identity_key(case: DomainDocument) -> str:
    return _identity_key(str(case.get("project_id") or ""), str(case.get("version_id") or ""), str(case.get("final_export_hash") or ""))

def _renderer_summary(manifest: DomainDocument) -> DomainDocument:
    for key in ("audio_artifact", "audio", "renderer", "audio_health"):
        value = manifest.get(key) if isinstance(manifest, dict) else None
        if isinstance(value, dict):
            renderer = _document_or(value.get("renderer"), value)
            if isinstance(renderer, dict) and renderer:
                result = dict(renderer)
                result.setdefault("runner_kind", "real")
                result.setdefault("release_ready", True)
                return result
    return {"runner_kind": "real", "release_ready": True, "profile_id": "final-export"}

def _renderer_release_ready(renderer: DomainDocument) -> bool:
    return renderer.get("runner_kind") == "real" and renderer.get("release_ready") is not False

def _read_optional_json(path: Path) -> DomainDocument:
    try:
        if path.exists():
            return read_json(path)
    except (OSError, ValueError):
        return {}
    return {}

def _readme(report: DomainDocument, matrix: DomainDocument, evidence: DomainDocument) -> str:
    summary = _as_document(report.get("summary"))
    return "\n".join(
        [
            "MusicForge Release Audio Certification",
            f"release_id: {report.get('release_id')}",
            f"campaign_id: {report.get('campaign_id')}",
            f"status: {report.get('status')}",
            f"tracks: {summary.get('track_count')}",
            f"manual accepted tracks: {summary.get('manual_accepted_track_count')}",
            f"real audio tracks: {summary.get('real_audio_track_count')}",
            f"evidence count: {evidence.get('summary', {}).get('evidence_count')}",
            "",
            "This package contains certification summaries only. It does not embed audio files or local .musicforge paths.",
            f"matrix_status: {matrix.get('status')}",
            "",
        ]
    )

def _file_record(path: Path, root: Path, rel: str) -> DomainDocument:
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

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _integrity_ok(payload: DomainDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)

def _semantic_hash(value: object) -> str:
    return stable_hash(_strip_semantic_volatile(value))

def _strip_semantic_volatile(value: object) -> object:
    if isinstance(value, dict):
        return {key: _strip_semantic_volatile(item) for key, item in value.items() if key not in {"generated_at", "integrity_hash"}}
    if isinstance(value, list):
        return [_strip_semantic_volatile(item) for item in value]
    return value

def _append_event(path: Path, event_type: str, payload: DomainDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = sanitize_metadata({"event_type": event_type, "created_at": now_iso(), **payload})
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

def _blocker_message(blocker: str) -> str:
    return {
        "audio_campaign_case_stale": "Campaign case source is stale.",
        "audio_campaign_wav_missing": "Campaign case is missing WAV evidence.",
        "test_fake_audio_not_release_ready": "Test fake WAV cannot count as release-ready audio.",
        "real_audio_required": "Release candidate campaign requires real renderer audio.",
        "synthetic_review_not_allowed": "Synthetic review cannot satisfy release candidate audio review.",
        "manual_review_missing": "Manual playback-confirmed review is missing.",
        "case_needs_fix": "Listening review needs fix.",
        "case_rejected": "Listening review rejected the track.",
        "minimum_rating_not_met": "Listening rating is below campaign threshold.",
        "open_high_or_critical_marker": "High or critical marker remains open.",
        "fix_sprint_missing": "Required Audio Fix Sprint is missing.",
        "fix_sprint_not_closed": "Required Audio Fix Sprint is not closed.",
        "fix_sprint_closeout_failed": "Required Audio Fix Sprint closeout failed.",
    }.get(blocker, blocker)
