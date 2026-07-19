# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
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
from song_agent.domains.quality.release_audio_certification import ReleaseAudioCertificationStore as ReleaseAudioCertificationStore
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package as verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_timeline_verifier import RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE as RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE, RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION as RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION, verify_release_audio_timeline_package as verify_release_audio_timeline_package, write_release_audio_timeline_verification_report as write_release_audio_timeline_verification_report
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

ReleaseAudioTimelineNotFoundError = _make_deferred_global('ReleaseAudioTimelineNotFoundError')
_case_identity_key = _make_deferred_global('_case_identity_key')
_checks = _make_deferred_global('_checks')
_derive_from_events = _make_deferred_global('_derive_from_events')
_event = _make_deferred_global('_event')
_event_ledger_hash = _make_deferred_global('_event_ledger_hash')
_identity_key = _make_deferred_global('_identity_key')
_integrity_hash = _make_deferred_global('_integrity_hash')
_read_optional_json = _make_deferred_global('_read_optional_json')
_renderer_release_ready = _make_deferred_global('_renderer_release_ready')
_sha256_path = _make_deferred_global('_sha256_path')
issue = _make_deferred_global('issue')
item = _make_deferred_global('item')
path = _make_deferred_global('path')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleaseAudioTimelineNotFoundError, _case_identity_key, _checks, _derive_from_events, _event, _event_ledger_hash, _identity_key, _integrity_hash
    global _read_optional_json, _renderer_release_ready, _sha256_path, issue, item, path, row
    ReleaseAudioTimelineNotFoundError = namespace.get('ReleaseAudioTimelineNotFoundError', ReleaseAudioTimelineNotFoundError)
    _case_identity_key = namespace.get('_case_identity_key', _case_identity_key)
    _checks = namespace.get('_checks', _checks)
    _derive_from_events = namespace.get('_derive_from_events', _derive_from_events)
    _event = namespace.get('_event', _event)
    _event_ledger_hash = namespace.get('_event_ledger_hash', _event_ledger_hash)
    _identity_key = namespace.get('_identity_key', _identity_key)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _renderer_release_ready = namespace.get('_renderer_release_ready', _renderer_release_ready)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    issue = namespace.get('issue', issue)
    item = namespace.get('item', item)
    path = namespace.get('path', path)
    row = namespace.get('row', row)
    _bind_deferred_defaults(namespace)






class ReleaseAudioTimelineStoreEvidenceMixin:
    def _with_timeline_id(self, docs: DomainDocument, release_id: str, timeline_id: str) -> DomainDocument:
        if docs["report"].get("timeline_id") == timeline_id:
            return docs
        events = []
        previous_hash = None
        for index, event in enumerate(docs["events"], start=1):
            payload = _as_document(event.get("payload"))
            rebuilt = _event(release_id, timeline_id, index, event.get("track_identity") or {}, str(event.get("event_type") or ""), str(event.get("status") or ""), str(event.get("severity") or "info"), payload, previous_hash)
            previous_hash = rebuilt["event_hash"]
            events.append(rebuilt)
        source_hash = docs["report"]["source_hash"]
        derived = _derive_from_events(release_id, timeline_id, events, source_hash=source_hash)
        docs["events"] = events
        docs["track_index"] = derived["track_index"]
        docs["trend"] = derived["trend"]
        docs["taxonomy"] = derived["taxonomy"]
        risks = derived["risks"]
        old_risks = docs.get("risks", {}).get("risks", [])
        for risk in old_risks:
            if risk not in risks["risks"]:
                risks["risks"].append(risk)
        risks["risks"] = sorted(risks["risks"], key=lambda item: str(item.get("risk_id") or ""))
        risks["summary"] = {"open_risk_count": len(risks["risks"]), "blocking_risk_count": sum(1 for row in risks["risks"] if str(row.get("severity") or "") in {"blocking", "critical"})}
        docs["risks"] = risks
        for key in ("track_index", "trend", "taxonomy", "risks"):
            docs[key]["timeline_id"] = timeline_id
            docs[key]["integrity_hash"] = _integrity_hash(docs[key])
        docs["bindings"]["timeline_id"] = timeline_id
        docs["bindings"]["integrity_hash"] = _integrity_hash(docs["bindings"])
        docs["report"]["timeline_id"] = timeline_id
        docs["report"]["event_ledger_hash"] = _event_ledger_hash(events)
        docs["report"]["summary"]["open_risk_count"] = docs["risks"]["summary"]["open_risk_count"]
        docs["report"]["summary"]["blocking_risk_count"] = docs["risks"]["summary"]["blocking_risk_count"]
        docs["report"]["status"] = "passed" if docs["report"]["summary"].get("certification_status") == "passed" and int(docs["report"]["summary"].get("blocking_risk_count") or 0) == 0 else "failed"
        docs["report"]["checks"] = _checks(docs["track_index"], docs["trend"], docs["risks"], docs["bindings"]["bindings"]["release_audio_certification"])
        docs["report"]["integrity_hash"] = _integrity_hash(docs["report"])
        return docs

    def _track_event_payload(self, release_id: str, track: object, campaign_report: DomainDocument, case_index: DomainDocument) -> DomainDocument:
        project_id = str(getattr(track, "project_id", "") or "")
        version_id = str(getattr(track, "version_id", "") or "")
        project_dir = self.project_store.project_dir(project_id)
        export_dir = final_export_dir(project_dir)
        manifest_path = export_dir / "manifest.json"
        wav_path = export_dir / "song.wav"
        current_manifest_hash = _sha256_path(manifest_path)
        wav_sha = _sha256_path(wav_path)
        final_export_hash = str(getattr(track, "final_export_hash", "") or "")
        identity_key = _identity_key(project_id, version_id, final_export_hash)
        cases = _as_list(case_index.get("cases"))
        case = next((item for item in cases if isinstance(item, dict) and _case_identity_key(item) == identity_key), {})
        report_cases = _as_list(campaign_report.get("cases"))
        report_case: object = next((item for item in report_cases if str(item.get("case_id") or "") == str(case.get("case_id") or "")), {})
        review = _as_document(report_case.get("review"))
        blockers = [str(item) for item in (report_case.get("blockers") or []) if isinstance(item, str)]
        review_status = str(review.get("status") or report_case.get("review_status") or report_case.get("status") or "missing")
        if review_status == "passed":
            review_status = str(case.get("review_status") or "accepted")
        manual_review = review.get("review_mode") == "manual" and review.get("playback_confirmed") is True and review_status == "accepted"
        real_audio = _renderer_release_ready(_as_document(report_case.get("renderer")))
        open_issues = 1 if review_status in {"needs_fix", "rejected"} else 0
        if final_export_hash and current_manifest_hash and final_export_hash != current_manifest_hash:
            blockers.append("release_track_final_export_stale")
        if not manual_review:
            blockers.append("manual_review_missing")
        if not real_audio:
            blockers.append("real_audio_missing")
        status = "certified" if not blockers and review_status == "accepted" else "needs_attention"
        track_row = sanitize_metadata(
            {
                "track_id": getattr(track, "track_id", None),
                "track_number": getattr(track, "track_number", None),
                "title": getattr(track, "title", None),
                "project_id": project_id,
                "version_id": version_id,
                "final_export_hash": final_export_hash,
                "current_final_export_hash": current_manifest_hash,
                "wav_sha256": wav_sha,
                "status": status,
                "event_count": 1,
                "fix_sprint_count": 1 if case.get("fix_sprint_id") else 0,
                "recheck_count": 1 if case.get("fix_sprint_id") else 0,
                "open_issue_count": open_issues,
                "resolved_issue_count": 0 if open_issues else len(blockers),
                "manual_review_count": 1 if manual_review else 0,
                "real_audio_review_count": 1 if real_audio else 0,
                "test_fake_count": 0 if real_audio else 1,
                "certification_status": "passed" if status == "certified" else "failed",
                "risk_level": "low" if status == "certified" else "high",
                "review_status": review_status,
            }
        )
        issues = [{"issue_key": item, "label": item.replace("_", " ").title(), "severity": "blocking", "status": "open"} for item in sorted(set(blockers))]
        risks: object = [
            {
                "risk_id": f"ratl-risk-{str(getattr(track, 'track_id', 'track')).replace('_', '-')}-{index:03d}",
                "severity": "blocking",
                "status": "open",
                "message": issue["label"],
                "track_id": getattr(track, "track_id", None),
                "evidence_event_ids": [],
                "recommended_action": "Refresh audio certification evidence and resolve timeline blocker.",
            }
            for index, issue in enumerate(issues, start=1)
        ]
        source = {"track_id": getattr(track, "track_id", None), "project_id": project_id, "version_id": version_id, "final_export_hash": final_export_hash, "current_final_export_hash": current_manifest_hash, "wav_sha256": wav_sha}
        return {"track": track_row, "issues": issues, "risks": risks, "source": source}

    def _current_certification_verification(self, release_id: str) -> DomainDocument:
        cert_zip = self.certification_store.zip_path(release_id)
        cert_verification_path = self.certification_store.verification_report_path(release_id)
        external_report = _read_optional_json(cert_verification_path)
        if not cert_zip.exists():
            return {
                "status": external_report.get("status") or "missing",
                "zip_sha256": external_report.get("zip_sha256"),
                "zip_size_bytes": external_report.get("zip_size_bytes"),
                "manifest_hash": external_report.get("manifest_hash"),
                "integrity_hash": external_report.get("integrity_hash"),
                "external_verification_status": external_report.get("status") or "missing",
                "external_verification_matches_current": False,
            }
        try:
            current = verify_release_audio_certification_package(
                cert_zip,
                strict=True,
                require_passed=True,
                require_signed=True,
                require_real_audio=True,
                require_manual_review=True,
                require_remediation_when_needed=True,
            )
        except Exception as exc:
            current = {"status": "failed", "error": str(exc)}
        external_integrity_ok = bool(external_report.get("integrity_hash")) and external_report.get("integrity_hash") == stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
        external_matches_current = (
            external_report.get("status") == "passed"
            and external_integrity_ok
            and external_report.get("zip_sha256") == current.get("zip_sha256")
            and external_report.get("zip_size_bytes") == current.get("zip_size_bytes")
            and external_report.get("manifest_hash") == current.get("manifest_hash")
        )
        if current.get("status") == "passed" and external_matches_current:
            return dict(external_report)
        failed = dict(current)
        failed["status"] = "failed"
        failed["external_verification_status"] = external_report.get("status") or "missing"
        failed["external_verification_report_hash"] = external_report.get("integrity_hash")
        failed["external_verification_matches_current"] = external_matches_current
        return failed

    def _current_timeline_id(self, release_id: str) -> str | None:
        current = _read_optional_json(self.current_path(release_id))
        value = str(current.get("timeline_id") or "")
        return value or None

    def _resolve_timeline_id(self, release_id: str, timeline_id: str | None) -> str:
        value = str(timeline_id or self._current_timeline_id(release_id) or "")
        if not value:
            raise ReleaseAudioTimelineNotFoundError(f"Release Audio Timeline not found for release: {release_id}.")
        return value

    def _next_timeline_id(self, release_id: str) -> str:
        root = self.timelines_root(release_id)
        root.mkdir(parents=True, exist_ok=True)
        existing = [path.name for path in root.iterdir() if path.is_dir() and path.name.startswith("ratl-")]
        return f"ratl-{len(existing) + 1:06d}"
