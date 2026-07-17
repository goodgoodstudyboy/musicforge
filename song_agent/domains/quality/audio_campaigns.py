from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document

import json as json
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.audio_campaign_verifier import verify_audio_campaign_package as verify_audio_campaign_package, write_audio_campaign_verification_report as write_audio_campaign_verification_report
from song_agent.domains.quality.audio_fix_sprints import AudioFixSprintNotFoundError as AudioFixSprintNotFoundError, AudioFixSprintStateError as AudioFixSprintStateError, AudioFixSprintStore as AudioFixSprintStore
from song_agent.domains.quality.audio_lab import AudioLabStore as AudioLabStore
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash


AUDIO_CAMPAIGN_ROOT = Path(".musicforge") / "audio-campaigns"
AUDIO_CAMPAIGN_SCHEMA_VERSION = 1
HIGH_SEVERITIES = {"high", "critical"}


class AudioCampaignError(ValueError):
    pass


class AudioCampaignNotFoundError(AudioCampaignError):
    pass


class AudioCampaignStateError(AudioCampaignError):
    pass


class AudioCampaignValidationError(AudioCampaignError):
    pass


class AudioCampaignStore:
    def __init__(
        self,
        root: Path | str = AUDIO_CAMPAIGN_ROOT,
        *,
        audio_lab_store: AudioLabStore | None = None,
        audio_fix_sprint_store: AudioFixSprintStore | None = None,
    ) -> None:
        self.root = Path(root)
        self.audio_lab_store = audio_lab_store or AudioLabStore()
        self.audio_fix_sprint_store = audio_fix_sprint_store or AudioFixSprintStore(audio_lab_store=self.audio_lab_store)
        self.lock = threading.RLock()

    def create_campaign(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        session_ids = _session_ids_from_payload(payload)
        settings = _settings_from_payload(payload)
        with self.lock:
            sessions = [self.audio_lab_store.read_session(session_id) for session_id in session_ids]
            campaign_id = self._next_id("acmp")
            now = now_iso()
            cases = _cases_from_sessions(sessions)
            if not cases:
                raise AudioCampaignStateError("Audio Campaign requires at least one Audio Lab session item.")
            source = _source_from_sessions(session_ids, sessions)
            campaign = sanitize_metadata(
                {
                    "schema_version": AUDIO_CAMPAIGN_SCHEMA_VERSION,
                    "campaign_id": campaign_id,
                    "name": _bounded(payload.get("name"), 160) or "Release Candidate Audio Campaign",
                    "profile": _bounded(payload.get("profile"), 80) or "release_candidate",
                    "status": "reviewing",
                    "created_at": now,
                    "updated_at": now,
                    "settings": settings,
                    "source": source,
                    "cases": cases,
                    "warnings": [],
                }
            )
            campaign["source_hash"] = stable_hash({"source": campaign["source"], "cases": [_case_source(case) for case in cases], "settings": settings})
            campaign["integrity_hash"] = _integrity_hash(campaign)
            self._write_campaign(campaign)
            self._write_case_index(campaign)
            _append_event(self.campaign_dir(campaign_id) / "events.jsonl", "audio_campaign_created", {"case_count": len(cases), "source_hash": campaign["source_hash"]})
            self.refresh_report(campaign_id)
            return self.read_campaign(campaign_id)

    def list_campaigns(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.root.glob("acmp-*/campaign.json"):
            try:
                campaign = read_json(path)
                rows.append(
                    {
                        "campaign_id": campaign.get("campaign_id"),
                        "name": campaign.get("name"),
                        "profile": campaign.get("profile"),
                        "status": campaign.get("status"),
                        "summary": campaign.get("summary", {}),
                        "created_at": campaign.get("created_at"),
                        "updated_at": campaign.get("updated_at"),
                    }
                )
            except (OSError, ValueError):
                continue
        return sorted(rows, key=lambda row: str(row.get("campaign_id") or ""))

    def read_campaign(self, campaign_id: str) -> dict[str, Any]:
        path = self.campaign_path(campaign_id)
        if not path.exists():
            raise AudioCampaignNotFoundError(f"Audio Campaign not found: {campaign_id}.")
        raw = read_json(path)
        if self._is_signed_campaign(raw, campaign_id):
            self._assert_signed_snapshot_valid(campaign_id, raw)
            return sanitize_metadata(raw)
        campaign = self._refresh_case_snapshots(raw, write=False)
        return sanitize_metadata(campaign)

    def refresh_campaign(self, campaign_id: str) -> dict[str, Any]:
        with self.lock:
            campaign = self._read_raw_campaign(campaign_id)
            if self._is_signed_campaign(campaign, campaign_id):
                raise AudioCampaignStateError("Signed Audio Campaign cannot be refreshed. Reset signoff before refreshing.")
            campaign = self._refresh_case_snapshots(self._read_raw_campaign(campaign_id), write=True)
            self.refresh_report(campaign_id)
            return self.read_campaign(campaign_id)

    def link_listening_session(self, campaign_id: str, session_id: str) -> dict[str, Any]:
        with self.lock:
            campaign = self._read_raw_campaign(campaign_id)
            if campaign.get("status") == "signed":
                raise AudioCampaignStateError("Signed Audio Campaign cannot be changed.")
            session_id = _validate_id(session_id, "als")
            session = self.audio_lab_store.read_session(session_id)
            existing_keys = {case.get("source_key") for case in campaign.get("cases", [])}
            new_cases = [case for case in _cases_from_sessions([session]) if case.get("source_key") not in existing_keys]
            if not new_cases:
                raise AudioCampaignStateError("Listening session does not add any new campaign cases.")
            start = len(campaign.get("cases", [])) + 1
            for offset, case in enumerate(new_cases):
                case["case_id"] = f"acc-{start + offset:06d}"
            campaign["cases"].extend(new_cases)
            session_ids = list(campaign.get("source", {}).get("session_ids") or [])
            if session_id not in session_ids:
                session_ids.append(session_id)
            sessions = [self.audio_lab_store.read_session(item) for item in session_ids]
            campaign["source"] = _source_from_sessions(session_ids, sessions)
            campaign["source_hash"] = stable_hash({"source": campaign["source"], "cases": [_case_source(case) for case in campaign.get("cases", [])], "settings": campaign.get("settings", {})})
            campaign["status"] = "reviewing"
            campaign["updated_at"] = now_iso()
            campaign["integrity_hash"] = _integrity_hash(campaign)
            self._write_campaign(campaign)
            self._write_case_index(campaign)
            _append_event(self.campaign_dir(campaign_id) / "events.jsonl", "audio_campaign_session_linked", {"session_id": session_id, "new_case_count": len(new_cases)})
            self.refresh_report(campaign_id)
            return self.read_campaign(campaign_id)

    def create_fix_sprints(self, campaign_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            campaign = self._refresh_case_snapshots(self._read_raw_campaign(campaign_id), write=True)
            if campaign.get("status") == "signed":
                raise AudioCampaignStateError("Signed Audio Campaign cannot create new fix sprints.")
            sessions_to_fix = _sessions_requiring_fix(campaign)
            if not sessions_to_fix:
                return {"campaign": self.read_campaign(campaign_id), "fix_sprints": [], "status": "passed"}
            created: list[dict[str, Any]] = []
            for session_id in sessions_to_fix:
                existing_id = _campaign_fix_sprint_for_session(campaign, session_id)
                if existing_id:
                    try:
                        created.append(self.audio_fix_sprint_store.read_sprint(existing_id))
                        continue
                    except AudioFixSprintNotFoundError:
                        pass
                try:
                    sprint = self.audio_fix_sprint_store.create_sprint(
                        {
                            "session_ids": [session_id],
                            "name": f"Audio Campaign {campaign_id} fix {session_id}",
                            "include_test_audio": bool((campaign.get("settings") or {}).get("allow_test_fake_audio")),
                        }
                    )
                except AudioFixSprintStateError:
                    sprint = _as_document(self._find_existing_sprint_for_session(session_id))
                    if not sprint:
                        raise
                created.append(sprint)
                for case in campaign.get("cases", []):
                    if case.get("session_id") == session_id and _case_requires_fix(case, campaign.get("settings", {})):
                        case.setdefault("fix", {})["fix_sprint_id"] = sprint.get("fix_sprint_id")
                        case["status"] = "fix_sprint_created"
            campaign["updated_at"] = now_iso()
            campaign["integrity_hash"] = _integrity_hash(campaign)
            self._write_campaign(campaign)
            self._write_case_index(campaign)
            _append_event(self.campaign_dir(campaign_id) / "events.jsonl", "audio_campaign_fix_sprints_created", {"count": len(created)})
            report = self.refresh_report(campaign_id)
            return {"campaign": self.read_campaign(campaign_id), "fix_sprints": created, "report": report, "status": report.get("status")}

    def refresh_report(self, campaign_id: str) -> dict[str, Any]:
        with self.lock:
            raw_campaign = self._read_raw_campaign(campaign_id)
            if self._is_signed_campaign(raw_campaign, campaign_id):
                self._assert_signed_snapshot_valid(campaign_id, raw_campaign)
                report_path = self.campaign_dir(campaign_id) / "campaign-report.json"
                if not report_path.exists():
                    raise AudioCampaignStateError("Signed Audio Campaign report is missing.")
                return read_json(report_path)
            campaign = self._refresh_case_snapshots(self._read_raw_campaign(campaign_id), write=True)
            report = _build_campaign_report(campaign, self.audio_fix_sprint_store)
            write_json(self.campaign_dir(campaign_id) / "campaign-report.json", report)
            campaign["summary"] = report.get("summary", {})
            if campaign.get("status") != "signed":
                campaign["status"] = "ready" if report.get("status") == "passed" else "needs_fix"
            campaign["report_hash"] = report.get("integrity_hash")
            campaign["updated_at"] = now_iso()
            campaign["integrity_hash"] = _integrity_hash(campaign)
            self._write_campaign(campaign)
            self._write_case_index(campaign)
            return report

    def signoff(self, campaign_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            campaign = self._read_raw_campaign(campaign_id)
            if campaign.get("status") == "signed" or self.signoff_path(campaign_id).exists():
                raise AudioCampaignStateError("Audio Campaign is already signed.")
            report = self.refresh_report(campaign_id)
            if report.get("status") != "passed":
                raise AudioCampaignStateError("Audio Campaign report has blockers.")
            campaign = self._read_raw_campaign(campaign_id)
            signed_by = _bounded(payload.get("signed_by") or payload.get("reviewer") or payload.get("name"), 120)
            if not signed_by:
                raise AudioCampaignValidationError("signed_by is required.")
            signoff = sanitize_metadata(
                {
                    "schema_version": AUDIO_CAMPAIGN_SCHEMA_VERSION,
                    "signoff_id": f"acs-{campaign_id}",
                    "campaign_id": campaign_id,
                    "status": "signed",
                    "signed_at": now_iso(),
                    "signed_by": signed_by,
                    "role": _bounded(payload.get("role"), 80) or "audio-reviewer",
                    "reason": _bounded(payload.get("reason"), 1000) or "Release candidate audio campaign accepted.",
                    "campaign_report_hash": report.get("integrity_hash"),
                    "case_index_hash": read_json(self.case_index_path(campaign_id)).get("integrity_hash"),
                    "source_hash": campaign.get("source_hash"),
                    "summary": report.get("summary", {}),
                }
            )
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(campaign_id), signoff)
            campaign = self._read_raw_campaign(campaign_id)
            campaign["status"] = "signed"
            campaign["signoff_hash"] = signoff["integrity_hash"]
            campaign["signed_at"] = signoff["signed_at"]
            campaign["updated_at"] = now_iso()
            campaign["integrity_hash"] = _integrity_hash(campaign)
            self._write_campaign(campaign)
            _append_event(self.campaign_dir(campaign_id) / "events.jsonl", "audio_campaign_signed", {"signoff_hash": signoff["integrity_hash"]})
            return {"campaign": self.read_campaign(campaign_id), "signoff": signoff, "report": report, "status": "signed"}

    def export_campaign(self, campaign_id: str) -> dict[str, Any]:
        with self.lock:
            raw_campaign = self._read_raw_campaign(campaign_id)
            signed = self._is_signed_campaign(raw_campaign, campaign_id)
            signoff_path = self.signoff_path(campaign_id)
            if signed:
                snapshot = self._assert_signed_snapshot_valid(campaign_id, raw_campaign)
                campaign = sanitize_metadata(snapshot["campaign"])
                report = snapshot["report"]
                case_index = snapshot["case_index"]
            else:
                report = self.refresh_report(campaign_id)
                campaign = sanitize_metadata(self._read_raw_campaign(campaign_id))
                case_index = read_json(self.case_index_path(campaign_id))
            export_dir = self.export_dir(campaign_id)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | str) -> None:
                path = export_dir / rel
                if isinstance(payload, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, export_dir, rel))

            write_entry("campaign-report.json", report)
            write_entry("case-index.json", case_index)
            if signoff_path.exists():
                write_entry("campaign-signoff.json", read_json(signoff_path))
            for case in campaign.get("cases", []):
                case_id = str(case.get("case_id"))
                write_entry(f"case-reports/{case_id}.json", sanitize_metadata(case))
            write_entry("README.md", _readme(campaign, report))
            manifest = sanitize_metadata(
                {
                    "package_type": "audio_campaign",
                    "schema_version": AUDIO_CAMPAIGN_SCHEMA_VERSION,
                    "campaign_id": campaign_id,
                    "generated_at": now_iso(),
                    "source_hash": campaign.get("source_hash"),
                    "campaign_report_hash": report.get("integrity_hash"),
                    "case_index_hash": case_index.get("integrity_hash"),
                    "signoff_hash": read_json(signoff_path).get("integrity_hash") if signoff_path.exists() else None,
                    "files": files,
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"campaign": campaign, "manifest": manifest, "export_dir": str(export_dir), "status": report.get("status")}

    def build_zip(self, campaign_id: str) -> dict[str, Any]:
        raw_campaign = self._read_raw_campaign(campaign_id)
        if self._is_signed_campaign(raw_campaign, campaign_id):
            self._assert_signed_snapshot_valid(campaign_id, raw_campaign)
        exported = self.export_campaign(campaign_id)
        export_dir = self.export_dir(campaign_id)
        zip_path = self.zip_path(campaign_id)
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(export_dir.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(export_dir).as_posix())
        with zipfile.ZipFile(zip_path) as zf:
            entries = sorted(item.filename for item in zf.infolist())
        manifest = read_json(export_dir / "manifest.json")
        manifest["zip"] = {
            "filename": zip_path.name,
            "size_bytes": zip_path.stat().st_size,
            "entry_count": len(entries),
            "entries": entries,
        }
        manifest["files"] = [_file_record(path, export_dir, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.relative_to(export_dir).as_posix() != "manifest.json"]
        manifest["integrity_hash"] = _integrity_hash(manifest)
        write_json(export_dir / "manifest.json", manifest)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(export_dir.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(export_dir).as_posix())
        return {"campaign": exported.get("campaign"), "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest, "status": exported.get("status")}

    def verify_zip(self, campaign_id: str, **kwargs: Any) -> dict[str, Any]:
        zip_path = self.zip_path(campaign_id)
        if not zip_path.exists():
            self.build_zip(campaign_id)
        report = verify_audio_campaign_package(zip_path, **kwargs)
        write_audio_campaign_verification_report(report, self.campaign_dir(campaign_id) / "audio-campaign-verification-report.json")
        return report

    def campaign_dir(self, campaign_id: str) -> Path:
        return self.root / _validate_id(campaign_id, "acmp")

    def campaign_path(self, campaign_id: str) -> Path:
        return self.campaign_dir(campaign_id) / "campaign.json"

    def case_index_path(self, campaign_id: str) -> Path:
        return self.campaign_dir(campaign_id) / "case-index.json"

    def signoff_path(self, campaign_id: str) -> Path:
        return self.campaign_dir(campaign_id) / "campaign-signoff.json"

    def export_dir(self, campaign_id: str) -> Path:
        return self.campaign_dir(campaign_id) / "export"

    def zip_path(self, campaign_id: str) -> Path:
        return self.campaign_dir(campaign_id) / "audio-campaign.zip"

    def _next_id(self, prefix: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.root.glob(f"{prefix}-*"):
            try:
                max_seen = max(max_seen, int(path.name.split("-")[-1]))
            except ValueError:
                continue
        return f"{prefix}-{max_seen + 1:06d}"

    def _read_raw_campaign(self, campaign_id: str) -> ImplementationDocument:
        path = self.campaign_path(campaign_id)
        if not path.exists():
            raise AudioCampaignNotFoundError(f"Audio Campaign not found: {campaign_id}.")
        return read_json(path)

    def _is_signed_campaign(self, campaign: ImplementationDocument, campaign_id: str) -> bool:
        return campaign.get("status") == "signed" or bool(campaign.get("signoff_hash")) or self.signoff_path(campaign_id).exists()

    def _assert_signed_snapshot_valid(self, campaign_id: str, campaign: ImplementationDocument | None = None) -> ImplementationDocument:
        campaign = campaign or self._read_raw_campaign(campaign_id)
        if campaign.get("status") != "signed":
            raise AudioCampaignStateError("Audio Campaign signoff state is inconsistent.")
        signoff_path = self.signoff_path(campaign_id)
        report_path = self.campaign_dir(campaign_id) / "campaign-report.json"
        case_index_path = self.case_index_path(campaign_id)
        if not signoff_path.exists():
            raise AudioCampaignStateError("Signed Audio Campaign signoff is missing.")
        if not report_path.exists():
            raise AudioCampaignStateError("Signed Audio Campaign report is missing.")
        if not case_index_path.exists():
            raise AudioCampaignStateError("Signed Audio Campaign case index is missing.")
        signoff = read_json(signoff_path)
        report = read_json(report_path)
        case_index = read_json(case_index_path)
        if not _integrity_ok(signoff):
            raise AudioCampaignStateError("Signed Audio Campaign signoff integrity failed.")
        if not _integrity_ok(report):
            raise AudioCampaignStateError("Signed Audio Campaign report integrity failed.")
        if not _integrity_ok(case_index):
            raise AudioCampaignStateError("Signed Audio Campaign case index integrity failed.")
        if signoff.get("status") != "signed":
            raise AudioCampaignStateError("Signed Audio Campaign signoff status is invalid.")
        if campaign.get("signoff_hash") and campaign.get("signoff_hash") != signoff.get("integrity_hash"):
            raise AudioCampaignStateError("Signed Audio Campaign signoff hash does not match campaign state.")
        if signoff.get("campaign_report_hash") != report.get("integrity_hash"):
            raise AudioCampaignStateError("Signed Audio Campaign report no longer matches signoff.")
        if signoff.get("case_index_hash") != case_index.get("integrity_hash"):
            raise AudioCampaignStateError("Signed Audio Campaign case index no longer matches signoff.")
        if signoff.get("source_hash") != campaign.get("source_hash"):
            raise AudioCampaignStateError("Signed Audio Campaign source no longer matches signoff.")
        return {"campaign": campaign, "signoff": signoff, "report": report, "case_index": case_index}

    def _write_campaign(self, campaign: ImplementationDocument) -> None:
        write_json(self.campaign_path(str(campaign.get("campaign_id"))), sanitize_metadata(campaign))

    def _write_case_index(self, campaign: ImplementationDocument) -> None:
        case_index = sanitize_metadata(
            {
                "schema_version": AUDIO_CAMPAIGN_SCHEMA_VERSION,
                "campaign_id": campaign.get("campaign_id"),
                "generated_at": now_iso(),
                "source_hash": campaign.get("source_hash"),
                "cases": [
                    {
                        "case_id": case.get("case_id"),
                        "session_id": case.get("session_id"),
                        "item_id": case.get("item_id"),
                        "song_id": case.get("song_id"),
                        "title": case.get("title"),
                        "project_id": case.get("project_id"),
                        "version_id": case.get("version_id"),
                        "final_export_hash": case.get("final_export_hash"),
                        "status": case.get("status"),
                        "source_hash": case.get("source_hash"),
                        "wav_sha256": case.get("artifact_hashes", {}).get("wav_sha256"),
                        "review_status": case.get("review", {}).get("status") if isinstance(case.get("review"), dict) else None,
                        "fix_sprint_id": case.get("fix", {}).get("fix_sprint_id") if isinstance(case.get("fix"), dict) else None,
                    }
                    for case in campaign.get("cases", [])
                ],
            }
        )
        case_index["integrity_hash"] = _integrity_hash(case_index)
        write_json(self.case_index_path(str(campaign.get("campaign_id"))), case_index)

    def _refresh_case_snapshots(self, campaign: ImplementationDocument, *, write: bool) -> ImplementationDocument:
        by_key = {}
        sessions = []
        for session_id in campaign.get("source", {}).get("session_ids", []):
            try:
                session = self.audio_lab_store.read_session(str(session_id))
                sessions.append(session)
                for case in _cases_from_sessions([session]):
                    by_key[case.get("source_key")] = case
            except Exception:
                continue
        stale = False
        refreshed = []
        for case in campaign.get("cases", []):
            current = by_key.get(case.get("source_key"))
            if current:
                fix = dict(case.get("fix") or {})
                current["fix"] = fix
                current["case_id"] = case.get("case_id")
                current["status"] = case.get("status") if fix else current.get("status")
                current["stale"] = current.get("source_hash") != case.get("source_hash") or bool(current.get("stale"))
                stale = stale or bool(current.get("stale"))
                refreshed.append(current)
            else:
                case["stale"] = True
                case.setdefault("stale_reasons", []).append("source_session_item_missing")
                stale = True
                refreshed.append(case)
        campaign["cases"] = refreshed
        if sessions:
            campaign["source"] = _source_from_sessions([str(session.get("session_id")) for session in sessions], sessions)
        campaign["stale"] = stale
        campaign["updated_at"] = now_iso()
        campaign["source_hash"] = stable_hash({"source": campaign.get("source"), "cases": [_case_source(case) for case in campaign.get("cases", [])], "settings": campaign.get("settings", {})})
        campaign["integrity_hash"] = _integrity_hash(campaign)
        if write:
            self._write_campaign(campaign)
            self._write_case_index(campaign)
        return campaign

    def _find_existing_sprint_for_session(self, session_id: str) -> ImplementationDocument | None:
        for row in self.audio_fix_sprint_store.list_sprints():
            sprint_id = str(row.get("fix_sprint_id") or "")
            try:
                sprint = self.audio_fix_sprint_store.read_sprint(sprint_id)
            except Exception:
                continue
            if session_id in (sprint.get("source", {}).get("session_ids") or []) and sprint.get("status") in {"open", "in_progress"}:
                return sprint
        return None


def _build_campaign_report(campaign: ImplementationDocument, fix_store: AudioFixSprintStore) -> ImplementationDocument:
    settings = _as_document(campaign.get("settings"))
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    case_reports: list[dict[str, Any]] = []
    summary = {
        "case_count": len(campaign.get("cases", [])),
        "accepted_count": 0,
        "needs_fix_count": 0,
        "rejected_count": 0,
        "manual_review_count": 0,
        "synthetic_review_count": 0,
        "real_audio_count": 0,
        "test_fake_count": 0,
        "missing_wav_count": 0,
        "open_high_marker_count": 0,
        "open_critical_marker_count": 0,
        "fix_sprint_count": 0,
        "open_fix_sprint_count": 0,
        "failed_fix_sprint_count": 0,
        "stale_case_count": 0,
    }
    for case in campaign.get("cases", []):
        case_blockers: list[str] = []
        renderer = _as_document(case.get("renderer"))
        review = _as_document(case.get("review"))
        markers = [marker for marker in case.get("markers", []) if isinstance(marker, dict)]
        wav_sha = case.get("artifact_hashes", {}).get("wav_sha256") if isinstance(case.get("artifact_hashes"), dict) else None
        if case.get("stale"):
            summary["stale_case_count"] += 1
            case_blockers.append("audio_campaign_case_stale")
        if not wav_sha:
            summary["missing_wav_count"] += 1
            case_blockers.append("audio_campaign_wav_missing")
        if renderer.get("runner_kind") == "real" and renderer.get("release_ready") is True:
            summary["real_audio_count"] += 1
        elif renderer.get("runner_kind") == "test_fake":
            summary["test_fake_count"] += 1
            if not settings.get("allow_test_fake_audio"):
                case_blockers.append("test_fake_audio_not_release_ready")
        elif settings.get("require_real_renderer"):
            case_blockers.append("real_audio_required")
        if review.get("review_mode") == "manual" and review.get("playback_confirmed") is True:
            summary["manual_review_count"] += 1
        elif review:
            summary["synthetic_review_count"] += 1
            if not settings.get("allow_synthetic_review"):
                case_blockers.append("synthetic_review_not_allowed")
        else:
            case_blockers.append("manual_review_missing")
        fix_sprint_id = case.get("fix", {}).get("fix_sprint_id") if isinstance(case.get("fix"), dict) else None
        fix_required = _case_requires_fix(case, settings)
        fix_passed = False
        if fix_required:
            if not fix_sprint_id:
                case_blockers.append("fix_sprint_missing")
            else:
                summary["fix_sprint_count"] += 1
                try:
                    sprint = fix_store.read_sprint(str(fix_sprint_id))
                    closeout = fix_store.closeout_report(str(fix_sprint_id))
                    if sprint.get("status") != "closed":
                        summary["open_fix_sprint_count"] += 1
                        case_blockers.append("fix_sprint_not_closed")
                    if closeout.get("status") != "passed":
                        summary["failed_fix_sprint_count"] += 1
                        case_blockers.append("fix_sprint_closeout_failed")
                    fix_passed = sprint.get("status") == "closed" and closeout.get("status") == "passed"
                except Exception:
                    summary["failed_fix_sprint_count"] += 1
                    case_blockers.append("fix_sprint_missing")
        status = str(review.get("status") or "")
        if status == "accepted":
            summary["accepted_count"] += 1
        elif status == "needs_fix":
            summary["needs_fix_count"] += 1
            if not fix_passed:
                case_blockers.append("case_needs_fix")
        elif status == "rejected":
            summary["rejected_count"] += 1
            if not fix_passed:
                case_blockers.append("case_rejected")
        if review and int(review.get("rating") or 0) < int(settings.get("minimum_rating") or 4) and not fix_passed:
            case_blockers.append("minimum_rating_not_met")
        high_or_critical = []
        for marker in markers:
            severity = str(marker.get("severity") or "")
            if severity in HIGH_SEVERITIES:
                high_or_critical.append(marker)
                if not fix_passed:
                    if severity == "high":
                        summary["open_high_marker_count"] += 1
                    if severity == "critical":
                        summary["open_critical_marker_count"] += 1
        if high_or_critical and settings.get("block_high_or_critical_markers") and not fix_passed:
            case_blockers.append("open_high_or_critical_marker")
        for blocker in sorted(set(case_blockers)):
            blockers.append({"check_id": blocker, "case_id": case.get("case_id"), "message": _blocker_message(blocker)})
        case_reports.append(
            {
                "case_id": case.get("case_id"),
                "session_id": case.get("session_id"),
                "item_id": case.get("item_id"),
                "song_id": case.get("song_id"),
                "title": case.get("title"),
                "status": "blocked" if case_blockers else "passed",
                "blockers": sorted(set(case_blockers)),
                "renderer": renderer,
                "review": _review_public(review),
                "marker_count": len(markers),
                "fix_sprint_id": fix_sprint_id,
                "source_hash": case.get("source_hash"),
            }
        )
    checks = _checks_from_summary(summary, blockers, settings)
    status = "passed" if not blockers else "failed"
    report = sanitize_metadata(
        {
            "schema_version": AUDIO_CAMPAIGN_SCHEMA_VERSION,
            "report_id": f"acr-{campaign.get('campaign_id')}",
            "campaign_id": campaign.get("campaign_id"),
            "generated_at": now_iso(),
            "status": status,
            "profile": campaign.get("profile"),
            "settings": settings,
            "source": {"campaign_source_hash": campaign.get("source_hash"), "session_ids": campaign.get("source", {}).get("session_ids", [])},
            "summary": summary,
            "checks": checks,
            "blockers": blockers,
            "warnings": warnings,
            "cases": case_reports,
        }
    )
    report["source_hash"] = stable_hash(report["source"])
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _checks_from_summary(summary: ImplementationDocument, blockers: list[ImplementationDocument], settings: ImplementationDocument) -> list[ImplementationDocument]:
    return [
        _check("audio_campaign_has_cases", int(summary.get("case_count") or 0) > 0, "Campaign contains at least one case."),
        _check("audio_campaign_real_audio", not settings.get("require_real_renderer") or int(summary.get("real_audio_count") or 0) == int(summary.get("case_count") or 0), "All cases use release-ready real audio."),
        _check("audio_campaign_manual_review", int(summary.get("manual_review_count") or 0) == int(summary.get("case_count") or 0), "All cases have manual review."),
        _check("audio_campaign_no_test_fake", settings.get("allow_test_fake_audio") or int(summary.get("test_fake_count") or 0) == 0, "No test fake WAV is counted as release-ready."),
        _check("audio_campaign_no_open_markers", not settings.get("block_high_or_critical_markers") or (int(summary.get("open_high_marker_count") or 0) + int(summary.get("open_critical_marker_count") or 0)) == 0, "No high or critical markers remain open."),
        _check("audio_campaign_fix_sprints_closed", int(summary.get("open_fix_sprint_count") or 0) == 0 and int(summary.get("failed_fix_sprint_count") or 0) == 0, "Required fix sprints are closed and passed."),
        _check("audio_campaign_no_blockers", not blockers, "Campaign has no blocking issues."),
    ]


def _cases_from_sessions(sessions: list[ImplementationDocument]) -> list[ImplementationDocument]:
    cases: list[dict[str, Any]] = []
    counter = 0
    for session in sessions:
        session_id = str(session.get("session_id") or "")
        for item in session.get("items", []):
            if not isinstance(item, dict):
                continue
            counter += 1
            case = sanitize_metadata(
                {
                    "case_id": f"acc-{counter:06d}",
                    "source_key": stable_hash({"session_id": session_id, "item_id": item.get("item_id")}),
                    "session_id": session_id,
                    "item_id": item.get("item_id"),
                    "song_id": item.get("song_id"),
                    "title": item.get("title"),
                    "project_id": item.get("project_id"),
                    "version_id": item.get("version_id"),
                    "final_export_hash": item.get("final_export_hash"),
                    "status": "reviewed" if item.get("review") else "needs_review",
                    "artifact_relpaths": dict(item.get("artifact_relpaths") or {}),
                    "artifact_hashes": dict(item.get("artifact_hashes") or {}),
                    "audio_status": item.get("audio_status"),
                    "renderer": dict(item.get("renderer") or {}),
                    "audio_health_summary": item.get("audio_health_summary") or {},
                    "music_health_summary": item.get("music_health_summary") or {},
                    "review": dict(item.get("review") or {}),
                    "markers": [dict(marker) for marker in item.get("markers", []) if isinstance(marker, dict)],
                    "stale": bool(item.get("stale") or session.get("stale")),
                    "source_hash": item.get("source_hash"),
                    "fix": {},
                }
            )
            cases.append(case)
    return cases


def _source_from_sessions(session_ids: list[str], sessions: list[ImplementationDocument]) -> ImplementationDocument:
    source = {
        "source_type": "audio_lab_sessions",
        "session_ids": session_ids,
        "session_hashes": {str(session.get("session_id")): session.get("source_hash") for session in sessions},
        "session_integrity_hashes": {str(session.get("session_id")): session.get("integrity_hash") for session in sessions},
    }
    source["source_hash"] = stable_hash(source)
    return source


def _settings_from_payload(payload: ImplementationDocument) -> ImplementationDocument:
    allow_test = bool(payload.get("allow_test_audio") or payload.get("allow_test_fake_audio"))
    return {
        "require_real_renderer": not allow_test and bool(payload.get("require_real_renderer", True)),
        "allow_test_fake_audio": allow_test,
        "allow_synthetic_review": bool(payload.get("allow_synthetic_review", False)),
        "minimum_rating": max(1, min(5, int(payload.get("minimum_rating") or 4))),
        "block_high_or_critical_markers": bool(payload.get("block_high_or_critical_markers", True)),
    }


def _session_ids_from_payload(payload: ImplementationDocument) -> list[str]:
    raw = payload.get("session_ids") or payload.get("from_sessions") or payload.get("from_session") or payload.get("session_id")
    if isinstance(raw, list):
        values = raw
    else:
        values = [raw]
    session_ids = [_validate_id(str(item), "als") for item in values if str(item or "").strip()]
    if not session_ids:
        raise AudioCampaignValidationError("At least one Audio Lab session is required.")
    return list(dict.fromkeys(session_ids))


def _sessions_requiring_fix(campaign: ImplementationDocument) -> list[str]:
    sessions = []
    settings = _as_document(campaign.get("settings"))
    for case in campaign.get("cases", []):
        if _case_requires_fix(case, settings):
            session_id = str(case.get("session_id") or "")
            if session_id and session_id not in sessions:
                sessions.append(session_id)
    return sessions


def _case_requires_fix(case: ImplementationDocument, settings: ImplementationDocument) -> bool:
    review = _as_document(case.get("review"))
    if review.get("status") in {"needs_fix", "rejected"}:
        return True
    if not settings.get("block_high_or_critical_markers", True):
        return False
    return any(str(marker.get("severity") or "") in HIGH_SEVERITIES for marker in case.get("markers", []) if isinstance(marker, dict))


def _campaign_fix_sprint_for_session(campaign: ImplementationDocument, session_id: str) -> str | None:
    for case in campaign.get("cases", []):
        if case.get("session_id") == session_id:
            sprint_id = case.get("fix", {}).get("fix_sprint_id") if isinstance(case.get("fix"), dict) else None
            if sprint_id:
                return str(sprint_id)
    return None


def _case_source(case: ImplementationDocument) -> ImplementationDocument:
    return {
        "case_id": case.get("case_id"),
        "session_id": case.get("session_id"),
        "item_id": case.get("item_id"),
        "source_hash": case.get("source_hash"),
        "artifact_hashes": case.get("artifact_hashes"),
        "renderer": case.get("renderer"),
        "review": _review_public(_as_document(case.get("review"))),
        "markers": [
            {"marker_id": marker.get("marker_id"), "severity": marker.get("severity"), "category": marker.get("category"), "source_hash": marker.get("source_hash")}
            for marker in case.get("markers", [])
            if isinstance(marker, dict)
        ],
        "fix_sprint_id": case.get("fix", {}).get("fix_sprint_id") if isinstance(case.get("fix"), dict) else None,
    }


def _review_public(review: ImplementationDocument) -> ImplementationDocument:
    return {
        "status": review.get("status"),
        "rating": review.get("rating"),
        "review_mode": review.get("review_mode"),
        "playback_confirmed": review.get("playback_confirmed"),
        "reviewer": review.get("reviewer"),
        "source_hash": review.get("source_hash"),
        "integrity_hash": review.get("integrity_hash"),
    }


def _check(check_id: str, passed: bool, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message}


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


def _readme(campaign: ImplementationDocument, report: ImplementationDocument) -> str:
    summary = _as_document(report.get("summary"))
    return "\n".join(
        [
            "# MusicForge Audio Campaign",
            "",
            f"Campaign: {campaign.get('campaign_id')}",
            f"Status: {report.get('status')}",
            f"Cases: {summary.get('case_count')}",
            f"Manual reviews: {summary.get('manual_review_count')}",
            f"Real audio: {summary.get('real_audio_count')}",
            "",
            "This package contains campaign evidence summaries only. It does not embed local .musicforge paths or audio files.",
            "",
        ]
    )


def _file_record(path: Path, root: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "sha256": _sha256_path(path), "size_bytes": path.stat().st_size}


def _append_event(path: Path, event_type: str, payload: ImplementationDocument) -> None:
    event = sanitize_metadata({"event_type": event_type, "created_at": now_iso(), "payload": payload})
    event["event_hash"] = stable_hash(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _validate_id(value: str, prefix: str) -> str:
    value = str(value or "").strip()
    if not value.startswith(prefix + "-"):
        raise AudioCampaignValidationError(f"Invalid {prefix} id.")
    safe = "".join(ch for ch in value if ch.isalnum() or ch in "-_")
    if safe != value:
        raise AudioCampaignValidationError(f"Invalid {prefix} id.")
    return value


def _sha256_path(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
