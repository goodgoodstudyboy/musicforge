from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document

import json as json
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.audio_campaign_analytics import AudioCampaignAnalyticsStore as AudioCampaignAnalyticsStore, build_audio_campaign_analytics as build_audio_campaign_analytics
from song_agent.domains.quality.audio_campaign_archive_verifier import verify_audio_campaign_archive_package as verify_audio_campaign_archive_package, write_audio_campaign_archive_verification_report as write_audio_campaign_archive_verification_report
from song_agent.domains.quality.audio_campaigns import AudioCampaignNotFoundError as AudioCampaignNotFoundError, AudioCampaignStateError as AudioCampaignStateError, AudioCampaignStore as AudioCampaignStore
from song_agent.domains.quality.audio_campaign_verifier import verify_audio_campaign_package as verify_audio_campaign_package
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash


AUDIO_CAMPAIGN_GOVERNANCE_SCHEMA_VERSION = 1


class AudioCampaignGovernanceError(ValueError):
    pass


class AudioCampaignGovernanceNotFoundError(AudioCampaignGovernanceError):
    pass


class AudioCampaignGovernanceStateError(AudioCampaignGovernanceError):
    pass


class AudioCampaignGovernanceStore:
    def __init__(
        self,
        campaign_store: AudioCampaignStore | None = None,
        analytics_store: AudioCampaignAnalyticsStore | None = None,
    ) -> None:
        self.campaign_store = campaign_store or AudioCampaignStore()
        self.analytics_store = analytics_store or AudioCampaignAnalyticsStore(self.campaign_store)
        self.lock = threading.RLock()

    def governance_dir(self, campaign_id: str) -> Path:
        return self.campaign_store.campaign_dir(campaign_id) / "governance"

    def archive_dir(self, campaign_id: str) -> Path:
        return self.campaign_store.campaign_dir(campaign_id) / "archive"

    def report_path(self, campaign_id: str) -> Path:
        return self.governance_dir(campaign_id) / "governance-report.json"

    def change_request_dir(self, campaign_id: str) -> Path:
        return self.governance_dir(campaign_id) / "change-requests"

    def reset_history_path(self, campaign_id: str) -> Path:
        return self.governance_dir(campaign_id) / "reset-history.jsonl"

    def archive_manifest_path(self, campaign_id: str) -> Path:
        return self.archive_dir(campaign_id) / "manifest.json"

    def archive_zip_path(self, campaign_id: str) -> Path:
        return self.archive_dir(campaign_id) / "audio-campaign-archive.zip"

    def archive_verification_report_path(self, campaign_id: str) -> Path:
        return self.archive_dir(campaign_id) / "audio-campaign-archive-verification-report.json"

    def refresh_governance_report(self, campaign_id: str) -> dict[str, Any]:
        with self.lock:
            source = self._source_state(campaign_id, ensure_zip=True, ensure_verification=True)
            report = _build_governance_report(campaign_id, source)
            write_json(self.report_path(campaign_id), report)
            return report

    def read_governance_report(self, campaign_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.report_path(campaign_id)
        if not path.exists():
            if default is not None:
                return default
            raise AudioCampaignGovernanceNotFoundError(f"Audio Campaign governance report not found: {campaign_id}.")
        return read_json(path)

    def create_change_request(self, campaign_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            source = self._source_state(campaign_id, ensure_zip=False, ensure_verification=False)
            signoff = _as_document(source.get("signoff"))
            if signoff.get("status") != "signed":
                raise AudioCampaignGovernanceStateError("Audio Campaign must be signed before creating a reset Change Request.")
            cr_id = self._next_change_request_id(campaign_id)
            now = now_iso()
            cr = sanitize_metadata(
                {
                    "schema_version": AUDIO_CAMPAIGN_GOVERNANCE_SCHEMA_VERSION,
                    "change_request_id": cr_id,
                    "campaign_id": campaign_id,
                    "status": "draft",
                    "created_at": now,
                    "created_by": _bounded(payload.get("created_by") or payload.get("requested_by") or "developer", 120),
                    "reason": _bounded(payload.get("reason"), 1000),
                    "risk": _bounded(payload.get("risk"), 40) or "medium",
                    "requested_actions": ["reset_audio_campaign_signoff"],
                    "source": {
                        "campaign_id": campaign_id,
                        "signoff_hash": signoff.get("integrity_hash"),
                        "campaign_report_hash": signoff.get("campaign_report_hash"),
                        "campaign_zip_sha256": source.get("campaign_zip_sha256"),
                    },
                    "approval": {},
                    "applied": {"applied_at": None, "reset_event_hash": None},
                }
            )
            cr["integrity_hash"] = _integrity_hash(cr)
            write_json(self.change_request_dir(campaign_id) / f"{cr_id}.json", cr)
            return cr

    def list_change_requests(self, campaign_id: str) -> list[dict[str, Any]]:
        rows = []
        for path in sorted(self.change_request_dir(campaign_id).glob("acrq-*.json")):
            try:
                rows.append(read_json(path))
            except (OSError, ValueError):
                continue
        return rows

    def approve_change_request(self, campaign_id: str, change_request_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            cr = self._read_change_request(campaign_id, change_request_id)
            if cr.get("status") not in {"draft", "submitted"}:
                raise AudioCampaignGovernanceStateError("Only draft or submitted Change Requests can be approved.")
            cr["status"] = "approved"
            cr["approval"] = {
                "approved_by": _bounded(payload.get("approved_by") or payload.get("reviewer") or "reviewer", 120),
                "approved_at": now_iso(),
                "reason": _bounded(payload.get("reason") or cr.get("reason"), 1000),
            }
            cr["integrity_hash"] = _integrity_hash(cr)
            write_json(self.change_request_dir(campaign_id) / f"{change_request_id}.json", cr)
            return cr

    def reset_signoff(self, campaign_id: str, change_request_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            campaign = self.campaign_store._read_raw_campaign(campaign_id)
            signoff_path = self.campaign_store.signoff_path(campaign_id)
            if not signoff_path.exists():
                raise AudioCampaignGovernanceStateError("Audio Campaign signoff does not exist.")
            signoff = read_json(signoff_path)
            cr = self._read_change_request(campaign_id, change_request_id)
            if not _integrity_ok(cr):
                raise AudioCampaignGovernanceStateError("Audio Campaign Change Request integrity failed.")
            if cr.get("status") != "approved":
                raise AudioCampaignGovernanceStateError("Audio Campaign reset requires an approved Change Request.")
            if cr.get("applied", {}).get("applied_at"):
                raise AudioCampaignGovernanceStateError("Audio Campaign Change Request has already been applied.")
            if cr.get("source", {}).get("signoff_hash") != signoff.get("integrity_hash"):
                raise AudioCampaignGovernanceStateError("Audio Campaign Change Request does not match current signoff.")
            event = sanitize_metadata(
                {
                    "event_type": "audio_campaign_signoff_reset",
                    "created_at": now_iso(),
                    "campaign_id": campaign_id,
                    "change_request_id": change_request_id,
                    "reason": _bounded(payload.get("reason") or cr.get("reason"), 1000),
                    "previous_signoff_hash": signoff.get("integrity_hash"),
                    "previous_campaign_status": campaign.get("status"),
                }
            )
            event["event_hash"] = stable_hash(event)
            _append_jsonl(self.reset_history_path(campaign_id), event)
            signoff_path.unlink()
            campaign["status"] = "needs_fix"
            campaign.pop("signoff_hash", None)
            campaign.pop("signed_at", None)
            campaign["updated_at"] = now_iso()
            campaign["integrity_hash"] = _integrity_hash(campaign)
            self.campaign_store._write_campaign(campaign)
            cr["status"] = "applied"
            cr["applied"] = {"applied_at": event["created_at"], "reset_event_hash": event["event_hash"]}
            cr["integrity_hash"] = _integrity_hash(cr)
            write_json(self.change_request_dir(campaign_id) / f"{change_request_id}.json", cr)
            return {"campaign": self.campaign_store.read_campaign(campaign_id), "change_request": cr, "reset_event": event, "status": "reset"}

    def refresh_analytics(self, campaign_id: str) -> dict[str, Any]:
        return self.analytics_store.refresh(campaign_id)

    def export_archive(self, campaign_id: str) -> dict[str, Any]:
        with self.lock:
            source = self._source_state(campaign_id, ensure_zip=True, ensure_verification=True)
            self._ensure_archive_mutable(campaign_id, source)
            analytics = self.analytics_store.read(campaign_id, default={}) or build_audio_campaign_analytics(source["campaign"], source["report"])
            if not analytics.get("integrity_hash"):
                analytics = build_audio_campaign_analytics(source["campaign"], source["report"])
                write_json(self.analytics_store.report_path(campaign_id), analytics)
            public_verification = _public_verification(source["verification"])
            governance = _build_governance_report(campaign_id, {**source, "analytics": analytics, "verification": public_verification})
            write_json(self.report_path(campaign_id), governance)
            archive_dir = self.archive_dir(campaign_id)
            archive_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | str) -> None:
                path = archive_dir / rel
                if isinstance(payload, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, archive_dir, rel))

            write_entry("campaign.json", _public_campaign(source["campaign"]))
            write_entry("campaign-report.json", source["report"])
            write_entry("case-index.json", source["case_index"])
            write_entry("campaign-signoff.json", source["signoff"])
            write_entry("audio-campaign-verification-report.json", public_verification)
            write_entry("governance-report.json", governance)
            write_entry("analytics-summary.json", analytics)
            write_entry("reset-history.jsonl", self._read_reset_history_text(campaign_id))
            write_entry("README.md", _archive_readme(source["campaign"], governance))
            manifest = sanitize_metadata(
                {
                    "package_type": "audio_campaign_archive",
                    "schema_version": AUDIO_CAMPAIGN_GOVERNANCE_SCHEMA_VERSION,
                    "campaign_id": campaign_id,
                    "generated_at": now_iso(),
                    "source": {
                        "campaign_signoff_hash": source["signoff"].get("integrity_hash"),
                        "campaign_report_hash": source["report"].get("integrity_hash"),
                        "case_index_hash": source["case_index"].get("integrity_hash"),
                        "campaign_source_hash": source["campaign"].get("source_hash"),
                        "campaign_zip_sha256": source.get("campaign_zip_sha256"),
                        "campaign_verification_hash": public_verification.get("integrity_hash"),
                        "governance_report_hash": governance.get("integrity_hash"),
                        "analytics_summary_hash": analytics.get("integrity_hash"),
                    },
                    "summary": governance.get("summary", {}),
                    "files": files,
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.archive_manifest_path(campaign_id), manifest)
            return manifest

    def build_archive_zip(self, campaign_id: str) -> dict[str, Any]:
        with self.lock:
            source = self._source_state(campaign_id, ensure_zip=True, ensure_verification=True)
            self._ensure_archive_mutable(campaign_id, source)
            manifest = self.export_archive(campaign_id)
            archive_dir = self.archive_dir(campaign_id)
            zip_path = self.archive_zip_path(campaign_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for path in sorted(archive_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        zf.write(path, path.relative_to(archive_dir).as_posix())
            with zipfile.ZipFile(zip_path) as zf:
                entries = sorted(item.filename for item in zf.infolist())
            manifest = read_json(self.archive_manifest_path(campaign_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, archive_dir, path.relative_to(archive_dir).as_posix()) for path in sorted(archive_dir.rglob("*")) if path.is_file() and path != zip_path and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.archive_manifest_path(campaign_id), manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for path in sorted(archive_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        zf.write(path, path.relative_to(archive_dir).as_posix())
            final_sha = _sha256_path(zip_path)
            event = {"event_type": "audio_campaign_archive_built", "created_at": now_iso(), "campaign_id": campaign_id, "signoff_hash": source["signoff"].get("integrity_hash"), "archive_zip_sha256": final_sha}
            event["event_hash"] = stable_hash(event)
            _append_jsonl(self.reset_history_path(campaign_id), event)
            return {"zip_path": str(zip_path), "zip_sha256": final_sha, "manifest": manifest, "status": "passed"}

    def verify_archive(self, campaign_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        report = verify_audio_campaign_archive_package(
            self.archive_zip_path(campaign_id),
            strict=bool(payload.get("strict", True)),
            require_signed=bool(payload.get("require_signed", True)),
            require_verification_passed=bool(payload.get("require_verification_passed", True)),
        )
        write_audio_campaign_archive_verification_report(report, self.archive_verification_report_path(campaign_id))
        return report

    def gate(self, campaign_id: str, *, required: bool = True, archive_zip_path: Path | str | None = None, archive_verification_report_path: Path | str | None = None) -> dict[str, Any]:
        try:
            source = self._source_state(campaign_id, ensure_zip=True, ensure_verification=True)
            archive_zip = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(campaign_id)
            verification_path = Path(archive_verification_report_path) if archive_verification_report_path else self.archive_verification_report_path(campaign_id)
            if not archive_zip.exists():
                return _gate_failed(required, "Audio Campaign Archive ZIP is missing.", campaign_id=campaign_id)
            if not verification_path.exists():
                return _gate_failed(required, "Audio Campaign Archive verification report is missing.", campaign_id=campaign_id)
            archive_verification = read_json(verification_path)
            current_verification = verify_audio_campaign_archive_package(archive_zip, strict=True, require_signed=True, require_verification_passed=True)
            if archive_verification.get("integrity_hash") != _integrity_hash(archive_verification):
                return _gate_failed(required, "Audio Campaign Archive verification report integrity failed.", campaign_id=campaign_id)
            if archive_verification.get("status") != "passed" or current_verification.get("status") != "passed":
                return _gate_failed(required, "Audio Campaign Archive verification failed.", campaign_id=campaign_id, verification_status=archive_verification.get("status"), current_status=current_verification.get("status"))
            if archive_verification.get("summary", {}).get("zip_sha256") != current_verification.get("summary", {}).get("zip_sha256"):
                return _gate_failed(required, "Audio Campaign Archive verification does not match current ZIP.", campaign_id=campaign_id)
            summary = _as_document(source["report"].get("summary"))
            blockers: list[str] = []
            case_count = _safe_int(summary.get("case_count"))
            if source["signoff"].get("status") != "signed":
                blockers.append("audio_campaign_not_signed")
            if source["report"].get("status") != "passed":
                blockers.append("audio_campaign_report_not_passed")
            if source["verification"].get("status") != "passed":
                blockers.append("audio_campaign_zip_verification_not_passed")
            if case_count <= 0:
                blockers.append("audio_campaign_no_cases")
            if _safe_int(summary.get("manual_review_count")) != case_count:
                blockers.append("audio_campaign_manual_review_incomplete")
            if _safe_int(summary.get("real_audio_count")) != case_count:
                blockers.append("audio_campaign_real_audio_incomplete")
            if _safe_int(summary.get("test_fake_count")):
                blockers.append("audio_campaign_test_fake_present")
            if _safe_int(summary.get("synthetic_review_count")):
                blockers.append("audio_campaign_synthetic_review_present")
            if blockers:
                return _gate_failed(required, "Audio Campaign governance gate failed.", campaign_id=campaign_id, blockers=blockers)
            return {
                "status": "passed",
                "hard_block": False,
                "message": "Audio Campaign governance gate passed.",
                "campaign_id": campaign_id,
                "campaign_signoff_hash": source["signoff"].get("integrity_hash"),
                "campaign_report_hash": source["report"].get("integrity_hash"),
                "archive_zip_sha256": current_verification.get("summary", {}).get("zip_sha256"),
                "archive_verification_hash": archive_verification.get("integrity_hash"),
                "summary": summary,
            }
        except (AudioCampaignNotFoundError, FileNotFoundError, AudioCampaignStateError, ValueError) as exc:
            return _gate_failed(required, str(exc), campaign_id=campaign_id)

    def _source_state(self, campaign_id: str, *, ensure_zip: bool, ensure_verification: bool) -> ImplementationDocument:
        campaign = self.campaign_store.read_campaign(campaign_id)
        if campaign.get("status") != "signed":
            raise AudioCampaignGovernanceStateError("Audio Campaign must be signed.")
        signoff = read_json(self.campaign_store.signoff_path(campaign_id))
        report = read_json(self.campaign_store.campaign_dir(campaign_id) / "campaign-report.json")
        case_index = read_json(self.campaign_store.case_index_path(campaign_id))
        if ensure_zip and not self.campaign_store.zip_path(campaign_id).exists():
            self.campaign_store.build_zip(campaign_id)
        if ensure_verification:
            verification = self.campaign_store.verify_zip(campaign_id, strict=True, require_real_audio=True, require_manual_review=True, require_fix_sprints_closed=True, require_signed=True, require_no_open_high=True, require_no_open_critical=True)
        else:
            verification_path = self.campaign_store.campaign_dir(campaign_id) / "audio-campaign-verification-report.json"
            verification = read_json(verification_path) if verification_path.exists() else {}
        zip_path = self.campaign_store.zip_path(campaign_id)
        return {
            "campaign": campaign,
            "signoff": signoff,
            "report": report,
            "case_index": case_index,
            "verification": verification,
            "campaign_zip_sha256": _sha256_path(zip_path) if zip_path.exists() else None,
        }

    def _ensure_archive_mutable(self, campaign_id: str, source: ImplementationDocument) -> None:
        signoff_hash = str(source.get("signoff", {}).get("integrity_hash") or "")
        if self._archive_built_for_signoff(campaign_id, signoff_hash):
            raise AudioCampaignGovernanceStateError("Audio Campaign Archive already exists for this signoff. Reset signoff before rebuilding archive.")

    def _archive_built_for_signoff(self, campaign_id: str, signoff_hash: str) -> bool:
        if not signoff_hash:
            return False
        built = False
        for event in self._read_reset_history(campaign_id):
            if event.get("event_type") == "audio_campaign_archive_built" and event.get("signoff_hash") == signoff_hash:
                built = True
            if event.get("event_type") == "audio_campaign_signoff_reset" and event.get("previous_signoff_hash") == signoff_hash:
                built = False
        return built

    def _read_change_request(self, campaign_id: str, change_request_id: str) -> ImplementationDocument:
        change_request_id = _validate_change_request_id(change_request_id)
        path = self.change_request_dir(campaign_id) / f"{change_request_id}.json"
        if not path.exists():
            raise AudioCampaignGovernanceNotFoundError(f"Audio Campaign Change Request not found: {change_request_id}.")
        return read_json(path)

    def _next_change_request_id(self, campaign_id: str) -> str:
        self.change_request_dir(campaign_id).mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.change_request_dir(campaign_id).glob("acrq-*.json"):
            try:
                max_seen = max(max_seen, int(path.stem.split("-")[-1]))
            except ValueError:
                continue
        return f"acrq-{max_seen + 1:06d}"

    def _read_reset_history(self, campaign_id: str) -> list[ImplementationDocument]:
        path = self.reset_history_path(campaign_id)
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
            except json.JSONDecodeError:
                continue
        return rows

    def _read_reset_history_text(self, campaign_id: str) -> str:
        path = self.reset_history_path(campaign_id)
        return path.read_text(encoding="utf-8") if path.exists() else ""


def _build_governance_report(campaign_id: str, source: ImplementationDocument) -> ImplementationDocument:
    report = _as_document(source.get("report"))
    summary = _as_document(report.get("summary"))
    verification = _as_document(source.get("verification"))
    signoff = _as_document(source.get("signoff"))
    blockers: list[dict[str, Any]] = []
    checks = [
        _check("audio_campaign_governance.signed", signoff.get("status") == "signed"),
        _check("audio_campaign_governance.report_passed", report.get("status") == "passed"),
        _check("audio_campaign_governance.verification_passed", verification.get("status") == "passed"),
        _check("audio_campaign_governance.manual_reviews", _safe_int(summary.get("case_count")) > 0 and _safe_int(summary.get("manual_review_count")) == _safe_int(summary.get("case_count"))),
        _check("audio_campaign_governance.real_audio", _safe_int(summary.get("case_count")) > 0 and _safe_int(summary.get("real_audio_count")) == _safe_int(summary.get("case_count"))),
        _check("audio_campaign_governance.no_fake_audio", _safe_int(summary.get("test_fake_count")) == 0),
        _check("audio_campaign_governance.no_synthetic_review", _safe_int(summary.get("synthetic_review_count")) == 0),
    ]
    for check in checks:
        if check["status"] == "failed":
            blockers.append({"check_id": check["check_id"], "message": check["message"]})
    governance = sanitize_metadata(
        {
            "schema_version": AUDIO_CAMPAIGN_GOVERNANCE_SCHEMA_VERSION,
            "campaign_id": campaign_id,
            "status": "signed" if not blockers else "blocked",
            "generated_at": now_iso(),
            "source": {
                "campaign_hash": source.get("campaign", {}).get("integrity_hash"),
                "campaign_source_hash": source.get("campaign", {}).get("source_hash"),
                "campaign_report_hash": report.get("integrity_hash"),
                "case_index_hash": source.get("case_index", {}).get("integrity_hash"),
                "signoff_hash": signoff.get("integrity_hash"),
                "campaign_zip_sha256": source.get("campaign_zip_sha256"),
                "campaign_verification_hash": verification.get("integrity_hash"),
            },
            "summary": {
                "case_count": summary.get("case_count", 0),
                "manual_review_count": summary.get("manual_review_count", 0),
                "real_audio_count": summary.get("real_audio_count", 0),
                "accepted_count": summary.get("accepted_count", 0),
                "fixed_case_count": summary.get("fix_sprint_count", 0),
                "open_blocker_count": len(report.get("blockers", []) if isinstance(report.get("blockers"), list) else []),
                "campaign_verification_status": verification.get("status") or "missing",
                "release_ready": not blockers,
            },
            "checks": checks,
            "blockers": blockers,
            "warnings": [],
        }
    )
    governance["source_hash"] = stable_hash(governance["source"])
    governance["integrity_hash"] = _integrity_hash(governance)
    return governance


def _gate_failed(required: bool, message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed" if required else "missing", "hard_block": bool(required), "message": message, **extra}


def _check(check_id: str, passed: bool) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": check_id.replace("_", " ")}


def _archive_readme(campaign: ImplementationDocument, governance: ImplementationDocument) -> str:
    return "\n".join(
        [
            "# MusicForge Audio Campaign Archive",
            "",
            f"Campaign: {campaign.get('campaign_id')}",
            f"Status: {governance.get('status')}",
            f"Cases: {governance.get('summary', {}).get('case_count')}",
            "",
            "This archive contains signed Audio Campaign governance evidence and summary metadata.",
            "",
        ]
    )


def _public_campaign(campaign: ImplementationDocument) -> ImplementationDocument:
    public = sanitize_metadata(campaign)
    for case in public.get("cases", []) if isinstance(public.get("cases"), list) else []:
        if not isinstance(case, dict):
            continue
        case.pop("artifact_relpaths", None)
    public["integrity_hash"] = _integrity_hash(public)
    return public


def _public_verification(verification: ImplementationDocument) -> ImplementationDocument:
    summary = _as_document(verification.get("summary"))
    public = sanitize_metadata(
        {
            "package_type": verification.get("package_type"),
            "status": verification.get("status"),
            "ok": verification.get("ok"),
            "summary": {
                "zip_sha256": summary.get("zip_sha256"),
                "zip_size_bytes": summary.get("zip_size_bytes"),
                "manifest_hash": summary.get("manifest_hash"),
                "campaign_id": summary.get("campaign_id"),
                "case_count": summary.get("case_count"),
                "check_count": summary.get("check_count"),
                "blocker_count": summary.get("blocker_count"),
                "warning_count": summary.get("warning_count"),
            },
            "blockers": verification.get("blockers", []),
            "warnings": verification.get("warnings", []),
        }
    )
    public["integrity_hash"] = _integrity_hash(public)
    return public


def _file_record(path: Path, root: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "sha256": _sha256_path(path), "size_bytes": path.stat().st_size}


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _validate_change_request_id(value: str) -> str:
    value = str(value or "").strip()
    if not value.startswith("acrq-"):
        raise AudioCampaignGovernanceStateError("Invalid Audio Campaign Change Request id.")
    safe = "".join(ch for ch in value if ch.isalnum() or ch in "-_")
    if safe != value:
        raise AudioCampaignGovernanceStateError("Invalid Audio Campaign Change Request id.")
    return value


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)


def _sha256_path(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
