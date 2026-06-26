from __future__ import annotations

import json
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.audio_campaign_governance import AudioCampaignGovernanceStore
from song_agent.audio_campaign_planner import AudioCampaignPlannerStore
from song_agent.audio_campaign_remediation import AudioCampaignRemediationStore
from song_agent.audio_campaigns import AudioCampaignStore
from song_agent.final_export import final_export_dir
from song_agent.projectio import read_json, write_json
from song_agent.projects import ProjectStore, now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.release_audio_certification import ReleaseAudioCertificationStore
from song_agent.release_audio_certification_verifier import verify_release_audio_certification_package
from song_agent.release_audio_timeline_verifier import (
    RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE,
    RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
    verify_release_audio_timeline_package,
    write_release_audio_timeline_verification_report,
)
from song_agent.releases import ReleaseStore, stable_hash


class ReleaseAudioTimelineError(ValueError):
    pass


class ReleaseAudioTimelineNotFoundError(ReleaseAudioTimelineError):
    pass


class ReleaseAudioTimelineStateError(ReleaseAudioTimelineError):
    pass


class ReleaseAudioTimelineValidationError(ReleaseAudioTimelineError):
    pass


class ReleaseAudioTimelineStore:
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

    def timelines_root(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-timelines"

    def timeline_dir(self, release_id: str, timeline_id: str) -> Path:
        return self.timelines_root(release_id) / timeline_id

    def current_path(self, release_id: str) -> Path:
        return self.timelines_root(release_id) / "current-timeline.json"

    def report_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "audio-timeline-report.json"

    def event_ledger_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "event-ledger.jsonl"

    def track_index_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "track-timeline-index.json"

    def trend_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "quality-trend.json"

    def taxonomy_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "issue-taxonomy.json"

    def risk_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "risk-register.json"

    def bindings_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "evidence-bindings.json"

    def signoff_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "timeline-signoff.json"

    def export_dir(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "export"

    def zip_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "release-audio-timeline.zip"

    def verification_report_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "verification-report.json"

    def list_timelines(self, release_id: str) -> dict[str, Any]:
        root = self.timelines_root(release_id)
        current = self._current_timeline_id(release_id)
        timelines = []
        if root.exists():
            for path in sorted(root.iterdir()):
                if path.is_dir() and path.name.startswith("ratl-"):
                    report = _read_optional_json(path / "audio-timeline-report.json")
                    signoff = _read_optional_json(path / "timeline-signoff.json")
                    timelines.append({"timeline_id": path.name, "status": report.get("status", "missing"), "signed": signoff.get("status") == "signed", "summary": report.get("summary", {})})
        return {"release_id": release_id, "current_timeline_id": current, "timelines": timelines}

    def read_timeline(self, release_id: str, timeline_id: str | None = None) -> dict[str, Any]:
        return sanitize_metadata(read_json(self.report_path(release_id, timeline_id)))

    def read_events(self, release_id: str, timeline_id: str | None = None) -> dict[str, Any]:
        events = _read_jsonl(self.event_ledger_path(release_id, timeline_id))
        return {"release_id": release_id, "timeline_id": self._resolve_timeline_id(release_id, timeline_id), "events": sanitize_metadata(events)}

    def read_track_index(self, release_id: str, timeline_id: str | None = None) -> dict[str, Any]:
        return sanitize_metadata(read_json(self.track_index_path(release_id, timeline_id)))

    def read_quality_trend(self, release_id: str, timeline_id: str | None = None) -> dict[str, Any]:
        return sanitize_metadata(read_json(self.trend_path(release_id, timeline_id)))

    def read_issue_taxonomy(self, release_id: str, timeline_id: str | None = None) -> dict[str, Any]:
        return sanitize_metadata(read_json(self.taxonomy_path(release_id, timeline_id)))

    def read_risk_register(self, release_id: str, timeline_id: str | None = None) -> dict[str, Any]:
        return sanitize_metadata(read_json(self.risk_path(release_id, timeline_id)))

    def read_evidence_bindings(self, release_id: str, timeline_id: str | None = None) -> dict[str, Any]:
        return sanitize_metadata(read_json(self.bindings_path(release_id, timeline_id)))

    def refresh_timeline(self, release_id: str, *, force_new: bool = False) -> dict[str, Any]:
        with self.lock:
            docs = self._build_documents(release_id, timeline_id=None)
            current_id = self._current_timeline_id(release_id)
            if current_id:
                current_report = _read_optional_json(self.report_path(release_id, current_id))
                current_signed = self.signoff_path(release_id, current_id).exists()
                same_source = current_report.get("source_hash") == docs["report"].get("source_hash")
                if current_signed and same_source and not force_new:
                    return {"status": current_report.get("status"), "timeline_id": current_id, "report": current_report, "current": True, "signed": True}
                if not current_signed and same_source and not force_new:
                    timeline_id = current_id
                else:
                    timeline_id = self._next_timeline_id(release_id)
            else:
                timeline_id = self._next_timeline_id(release_id)
            docs = self._with_timeline_id(docs, release_id, timeline_id)
            self._write_documents(release_id, timeline_id, docs)
            self._write_current(release_id, timeline_id, docs["report"])
            return {"status": docs["report"].get("status"), "timeline_id": timeline_id, "report": docs["report"], "current": True, "signed": False}

    def signoff_timeline(self, release_id: str, timeline_id: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            timeline_id = self._resolve_timeline_id(release_id, timeline_id)
            self._assert_current_or_stale_safe(release_id, timeline_id)
            if self.signoff_path(release_id, timeline_id).exists():
                raise ReleaseAudioTimelineStateError("Release Audio Timeline is already signed.")
            report, track_index, events, trend, taxonomy, risks, bindings = self._read_document_set(release_id, timeline_id)
            if report.get("status") == "failed":
                raise ReleaseAudioTimelineStateError("Release Audio Timeline has blockers.")
            if int((risks.get("summary") or {}).get("blocking_risk_count") or 0) > 0:
                raise ReleaseAudioTimelineStateError("Release Audio Timeline has blocking risks.")
            if ((bindings.get("bindings") or {}).get("release_audio_certification") or {}).get("status") != "passed":
                raise ReleaseAudioTimelineStateError("Release Audio Timeline Certification evidence is not passed.")
            signoff = sanitize_metadata(
                {
                    "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
                    "signoff_id": f"ratls-{timeline_id}",
                    "release_id": release_id,
                    "timeline_id": timeline_id,
                    "status": "signed",
                    "signed_at": now_iso(),
                    "signed_by": _bounded(payload.get("signed_by") or payload.get("reviewer") or "audio-timeline", 120),
                    "role": _bounded(payload.get("role") or "audio-timeline-reviewer", 80),
                    "reason": _bounded(payload.get("reason") or "Release audio timeline accepted.", 1000),
                    "source_hash": report.get("source_hash"),
                    "timeline_report_hash": report.get("integrity_hash"),
                    "event_ledger_hash": _event_ledger_hash(events),
                    "track_index_hash": track_index.get("integrity_hash"),
                    "quality_trend_hash": trend.get("integrity_hash"),
                    "issue_taxonomy_hash": taxonomy.get("integrity_hash"),
                    "risk_register_hash": risks.get("integrity_hash"),
                    "evidence_bindings_hash": bindings.get("integrity_hash"),
                    "summary": report.get("summary", {}),
                }
            )
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(release_id, timeline_id), signoff)
            self._write_current(release_id, timeline_id, report)
            return {"status": "signed", "timeline_id": timeline_id, "signoff": signoff, "report": report}

    def export_timeline(self, release_id: str, timeline_id: str | None = None) -> dict[str, Any]:
        with self.lock:
            timeline_id = self._resolve_timeline_id(release_id, timeline_id)
            self._assert_current_or_stale_safe(release_id, timeline_id)
            report, track_index, events, trend, taxonomy, risks, bindings = self._read_document_set(release_id, timeline_id)
            signoff = _read_optional_json(self.signoff_path(release_id, timeline_id))
            export_dir = self.export_dir(release_id, timeline_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | list[dict[str, Any]] | str) -> None:
                path = export_dir / rel
                if isinstance(payload, str):
                    path.write_text(payload, encoding="utf-8")
                elif rel.endswith(".jsonl"):
                    path.write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in payload) + "\n", encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, export_dir, rel))

            write_entry("audio-timeline-report.json", report)
            write_entry("track-timeline-index.json", track_index)
            write_entry("event-ledger.jsonl", events)
            write_entry("quality-trend.json", trend)
            write_entry("issue-taxonomy.json", taxonomy)
            write_entry("risk-register.json", risks)
            write_entry("evidence-bindings.json", bindings)
            if signoff:
                write_entry("timeline-signoff.json", signoff)
            write_entry("README.txt", _readme(report, track_index, trend, risks))
            manifest = sanitize_metadata(
                {
                    "package_type": RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE,
                    "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
                    "release_id": release_id,
                    "timeline_id": timeline_id,
                    "generated_at": now_iso(),
                    "source_hash": report.get("source_hash"),
                    "report_hash": report.get("integrity_hash"),
                    "track_index_hash": track_index.get("integrity_hash"),
                    "event_ledger_hash": _event_ledger_hash(events),
                    "quality_trend_hash": trend.get("integrity_hash"),
                    "issue_taxonomy_hash": taxonomy.get("integrity_hash"),
                    "risk_register_hash": risks.get("integrity_hash"),
                    "evidence_bindings_hash": bindings.get("integrity_hash"),
                    "signoff_hash": signoff.get("integrity_hash") if signoff else None,
                    "summary": report.get("summary", {}),
                    "files": files,
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": report.get("status"), "timeline_id": timeline_id, "export_dir": str(export_dir), "manifest": manifest}

    def build_zip(self, release_id: str, timeline_id: str | None = None) -> dict[str, Any]:
        with self.lock:
            timeline_id = self._resolve_timeline_id(release_id, timeline_id)
            exported = self.export_timeline(release_id, timeline_id)
            export_dir = self.export_dir(release_id, timeline_id)
            zip_path = self.zip_path(release_id, timeline_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(item.filename for item in archive.infolist())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, export_dir, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            return {"status": exported.get("status"), "timeline_id": timeline_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_zip(self, release_id: str, timeline_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        with self.lock:
            timeline_id = self._resolve_timeline_id(release_id, timeline_id)
            self._assert_current_or_stale_safe(release_id, timeline_id)
            if not self.zip_path(release_id, timeline_id).exists():
                self.build_zip(release_id, timeline_id)
            if kwargs.get("require_current_certification") and not kwargs.get("release_audio_certification_path"):
                kwargs["release_audio_certification_path"] = self.certification_store.zip_path(release_id)
            if kwargs.get("require_current_certification") and not kwargs.get("release_audio_certification_verification_report_path"):
                kwargs["release_audio_certification_verification_report_path"] = self.certification_store.verification_report_path(release_id)
            report = verify_release_audio_timeline_package(self.zip_path(release_id, timeline_id), **kwargs)
            write_release_audio_timeline_verification_report(report, self.verification_report_path(release_id, timeline_id))
            return report

    def gate(self, release_id: str, *, required: bool, require_signed: bool = False, require_current_certification: bool = True) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            timeline_id = self._current_timeline_id(release_id)
            if not timeline_id:
                refreshed = self.refresh_timeline(release_id)
                timeline_id = str(refreshed.get("timeline_id") or "")
            self._assert_current_or_stale_safe(release_id, timeline_id)
            report = self.read_timeline(release_id, timeline_id)
            signoff = _read_optional_json(self.signoff_path(release_id, timeline_id))
            if report.get("status") == "failed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Timeline has blockers.", "timeline_id": timeline_id, "report": report}
            if require_signed and signoff.get("status") != "signed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Timeline signoff is missing.", "timeline_id": timeline_id, "report": report}
            if require_current_certification:
                bindings = self.read_evidence_bindings(release_id, timeline_id)
                cert = ((bindings.get("bindings") or {}).get("release_audio_certification") or {}) if isinstance(bindings.get("bindings"), dict) else {}
                if cert.get("status") != "passed":
                    return {"status": "failed", "hard_block": True, "message": "Release Audio Timeline Certification binding is not passed.", "timeline_id": timeline_id, "report": report}
            return {"status": "passed", "hard_block": False, "message": "Release Audio Timeline gate passed.", "timeline_id": timeline_id, "report": report, "summary": report.get("summary", {}), "signoff": signoff or None}
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(str(exc))}

    def _write_documents(self, release_id: str, timeline_id: str, docs: dict[str, Any]) -> None:
        root = self.timeline_dir(release_id, timeline_id)
        root.mkdir(parents=True, exist_ok=True)
        write_json(root / "audio-timeline-report.json", docs["report"])
        write_json(root / "track-timeline-index.json", docs["track_index"])
        _write_jsonl(root / "event-ledger.jsonl", docs["events"])
        write_json(root / "quality-trend.json", docs["trend"])
        write_json(root / "issue-taxonomy.json", docs["taxonomy"])
        write_json(root / "risk-register.json", docs["risks"])
        write_json(root / "evidence-bindings.json", docs["bindings"])

    def _write_current(self, release_id: str, timeline_id: str, report: dict[str, Any]) -> None:
        current = {"schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION, "release_id": release_id, "timeline_id": timeline_id, "source_hash": report.get("source_hash"), "status": report.get("status"), "updated_at": now_iso()}
        current["integrity_hash"] = _integrity_hash(current)
        write_json(self.current_path(release_id), current)

    def _read_document_set(self, release_id: str, timeline_id: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        return (
            sanitize_metadata(read_json(self.report_path(release_id, timeline_id))),
            sanitize_metadata(read_json(self.track_index_path(release_id, timeline_id))),
            sanitize_metadata(_read_jsonl(self.event_ledger_path(release_id, timeline_id))),
            sanitize_metadata(read_json(self.trend_path(release_id, timeline_id))),
            sanitize_metadata(read_json(self.taxonomy_path(release_id, timeline_id))),
            sanitize_metadata(read_json(self.risk_path(release_id, timeline_id))),
            sanitize_metadata(read_json(self.bindings_path(release_id, timeline_id))),
        )

    def _assert_current_or_stale_safe(self, release_id: str, timeline_id: str) -> None:
        report = _read_optional_json(self.report_path(release_id, timeline_id))
        if not report:
            raise ReleaseAudioTimelineNotFoundError(f"Release Audio Timeline not found: {timeline_id}.")
        current_docs = self._with_timeline_id(self._build_documents(release_id, timeline_id=timeline_id), release_id, timeline_id)
        if current_docs["report"].get("source_hash") != report.get("source_hash") or current_docs["report"].get("status") != report.get("status"):
            raise ReleaseAudioTimelineStateError("Release Audio Timeline source is stale. Refresh timeline before using timeline evidence.")
        _report, track_index, events, trend, taxonomy, risks, bindings = self._read_document_set(release_id, timeline_id)
        if _semantic_hash(track_index) != _semantic_hash(current_docs["track_index"]) or _semantic_hash(events) != _semantic_hash(current_docs["events"]) or _semantic_hash(trend) != _semantic_hash(current_docs["trend"]) or _semantic_hash(taxonomy) != _semantic_hash(current_docs["taxonomy"]) or _semantic_hash(risks) != _semantic_hash(current_docs["risks"]) or _semantic_hash(bindings) != _semantic_hash(current_docs["bindings"]):
            raise ReleaseAudioTimelineStateError("Release Audio Timeline documents are stale. Refresh timeline before using timeline evidence.")

    def _build_documents(self, release_id: str, timeline_id: str | None) -> dict[str, Any]:
        release = self.release_store.get_release(release_id)
        timeline_id = timeline_id or "ratl-pending"
        certification_report = self.certification_store.read_report(release_id, default={})
        cert_zip = self.certification_store.zip_path(release_id)
        cert_verification = self._current_certification_verification(release_id)
        cert_binding = {
            "zip_sha256": _sha256_path(cert_zip),
            "zip_size_bytes": cert_zip.stat().st_size if cert_zip.exists() else None,
            "manifest_hash": cert_verification.get("manifest_hash"),
            "verification_report_hash": cert_verification.get("integrity_hash"),
            "status": cert_verification.get("status") or certification_report.get("status") or "missing",
            "report_hash": certification_report.get("integrity_hash"),
        }
        track_rows = []
        events: list[dict[str, Any]] = []
        blocker_risks: list[dict[str, Any]] = []
        link = self.planner_store.read_link(release_id, default={})
        campaign_id = str(link.get("campaign_id") or certification_report.get("campaign_id") or "")
        campaign_report = self.campaign_store.refresh_report(campaign_id) if campaign_id else {}
        case_index = _read_optional_json(self.campaign_store.case_index_path(campaign_id)) if campaign_id else {}
        remediation_gate = self.remediation_store.gate(release_id, required=False, require_signed=True)
        governance_gate = self.governance_store.gate(campaign_id, required=False) if campaign_id else {"status": "missing"}
        source_tracks = []
        previous_hash: str | None = None
        seq = 1
        for track in release.tracks:
            row = self._track_event_payload(release_id, track, campaign_report, case_index)
            track_rows.append(row["track"])
            source_tracks.append(row["source"])
            for risk in row["risks"]:
                blocker_risks.append(risk)
            event = _event(release_id, timeline_id, seq, row["track"], "track_certification_summary", row["track"].get("status", "unknown"), "info" if row["track"].get("status") == "certified" else "warning", row, previous_hash)
            previous_hash = event["event_hash"]
            events.append(event)
            seq += 1
        cert_event_payload = {"certification": cert_binding, "report_status": certification_report.get("status"), "governance_status": governance_gate.get("status"), "remediation_status": remediation_gate.get("status")}
        event = _event(release_id, timeline_id, seq, {}, "release_audio_certification_verified", str(cert_binding.get("status") or "missing"), "info" if cert_binding.get("status") == "passed" else "blocking", cert_event_payload, previous_hash)
        events.append(event)

        source = {
            "release_id": release_id,
            "track_sources_hash": stable_hash(source_tracks),
            "campaign_id": campaign_id or None,
            "campaign_report_hash": campaign_report.get("integrity_hash"),
            "case_index_hash": case_index.get("integrity_hash"),
            "governance_gate_hash": stable_hash(governance_gate),
            "remediation_gate_hash": stable_hash(remediation_gate),
            "certification_report_hash": certification_report.get("integrity_hash"),
            "certification_verification_hash": cert_verification.get("integrity_hash"),
            "certification_zip_sha256": cert_binding.get("zip_sha256"),
        }
        source["source_hash"] = stable_hash(source)
        derived = _derive_from_events(release_id, timeline_id, events, source_hash=source["source_hash"])
        track_index = derived["track_index"]
        trend = derived["trend"]
        taxonomy = derived["taxonomy"]
        risks = derived["risks"]
        for risk in blocker_risks:
            if risk not in risks["risks"]:
                risks["risks"].append(risk)
        risks["risks"] = sorted(risks["risks"], key=lambda item: str(item.get("risk_id") or ""))
        risks["summary"] = {"open_risk_count": len(risks["risks"]), "blocking_risk_count": sum(1 for row in risks["risks"] if str(row.get("severity") or "") in {"blocking", "critical"})}
        for doc in (track_index, trend, taxonomy, risks):
            doc["source_hash"] = source["source_hash"]
            doc["integrity_hash"] = _integrity_hash(doc)
        bindings = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
                "release_id": release_id,
                "timeline_id": timeline_id,
                "bindings": {
                    "release_audio_certification": cert_binding,
                    "audio_campaign_governance": {"campaign_id": campaign_id or None, "status": governance_gate.get("status"), "archive_zip_sha256": governance_gate.get("archive_zip_sha256"), "verification_report_hash": governance_gate.get("archive_verification_hash")},
                    "audio_campaign_remediation": {"needed": remediation_gate.get("needed"), "status": remediation_gate.get("status"), "message": remediation_gate.get("message")},
                    "final_exports": source_tracks,
                },
                "source_hash": source["source_hash"],
            }
        )
        bindings["integrity_hash"] = _integrity_hash(bindings)
        blocking_risk_count = int(risks["summary"].get("blocking_risk_count") or 0)
        cert_ok = cert_binding.get("status") == "passed"
        status = "passed" if cert_ok and blocking_risk_count == 0 and int(track_index["summary"].get("track_count") or 0) > 0 else "failed"
        report = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
                "timeline_id": timeline_id,
                "release_id": release_id,
                "campaign_id": campaign_id or None,
                "status": status,
                "generated_at": now_iso(),
                "source": source,
                "source_hash": source["source_hash"],
                "event_ledger_hash": _event_ledger_hash(events),
                "certification": cert_binding,
                "summary": {
                    **track_index.get("summary", {}),
                    "issue_type_count": taxonomy["summary"].get("issue_type_count"),
                    "open_risk_count": risks["summary"].get("open_risk_count"),
                    "blocking_risk_count": blocking_risk_count,
                    "certification_status": cert_binding.get("status"),
                    "governance_status": governance_gate.get("status"),
                    "remediation_status": remediation_gate.get("status"),
                },
                "checks": _checks(track_index, trend, risks, cert_binding),
            }
        )
        report["integrity_hash"] = _integrity_hash(report)
        return {"report": report, "track_index": track_index, "events": events, "trend": trend, "taxonomy": taxonomy, "risks": risks, "bindings": bindings}

    def _with_timeline_id(self, docs: dict[str, Any], release_id: str, timeline_id: str) -> dict[str, Any]:
        if docs["report"].get("timeline_id") == timeline_id:
            return docs
        events = []
        previous_hash = None
        for index, event in enumerate(docs["events"], start=1):
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
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

    def _track_event_payload(self, release_id: str, track: Any, campaign_report: dict[str, Any], case_index: dict[str, Any]) -> dict[str, Any]:
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
        cases = case_index.get("cases") if isinstance(case_index.get("cases"), list) else []
        case = next((item for item in cases if isinstance(item, dict) and _case_identity_key(item) == identity_key), {})
        report_cases = campaign_report.get("cases") if isinstance(campaign_report.get("cases"), list) else []
        report_case = next((item for item in report_cases if str(item.get("case_id") or "") == str(case.get("case_id") or "")), {})
        review = report_case.get("review") if isinstance(report_case.get("review"), dict) else {}
        blockers = [str(item) for item in (report_case.get("blockers") or []) if isinstance(item, str)]
        review_status = str(review.get("status") or report_case.get("review_status") or report_case.get("status") or "missing")
        if review_status == "passed":
            review_status = str(case.get("review_status") or "accepted")
        manual_review = review.get("review_mode") == "manual" and review.get("playback_confirmed") is True and review_status == "accepted"
        real_audio = _renderer_release_ready(report_case.get("renderer") if isinstance(report_case.get("renderer"), dict) else {})
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
        risks = [
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

    def _current_certification_verification(self, release_id: str) -> dict[str, Any]:
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


def _checks(track_index: dict[str, Any], trend: dict[str, Any], risks: dict[str, Any], cert_binding: dict[str, Any]) -> list[dict[str, Any]]:
    summary = track_index.get("summary") if isinstance(track_index.get("summary"), dict) else {}
    track_count = int(summary.get("track_count") or 0)
    return [
        {"check_id": "release_audio_timeline_tracks_present", "status": "passed" if track_count > 0 else "failed", "message": "Release timeline has tracks."},
        {"check_id": "release_audio_timeline_manual_reviews", "status": "passed" if int(summary.get("manual_review_count") or 0) >= track_count and track_count else "failed", "message": "Timeline has manual review coverage."},
        {"check_id": "release_audio_timeline_real_audio", "status": "passed" if int(summary.get("real_audio_review_count") or 0) >= track_count and track_count else "failed", "message": "Timeline has real audio coverage."},
        {"check_id": "release_audio_timeline_certification", "status": "passed" if cert_binding.get("status") == "passed" else "failed", "message": "Timeline binds passed Release Audio Certification."},
        {"check_id": "release_audio_timeline_no_blocking_risks", "status": "passed" if int((risks.get("summary") or {}).get("blocking_risk_count") or 0) == 0 else "failed", "message": "Timeline has no blocking risks."},
        {"check_id": "release_audio_timeline_quality_trend", "status": "passed" if (trend.get("summary") or {}).get("real_audio_coverage", 0) == 1.0 else "warning", "message": "Timeline quality trend is release-ready."},
    ]


def _event(release_id: str, timeline_id: str, sequence: int, track_identity: dict[str, Any], event_type: str, status: str, severity: str, payload: dict[str, Any], previous_event_hash: str | None) -> dict[str, Any]:
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


def _derive_from_events(release_id: Any, timeline_id: Any, events: list[dict[str, Any]], *, source_hash: Any) -> dict[str, Any]:
    from song_agent.release_audio_timeline_verifier import _derive_from_events as derive

    return derive(release_id, timeline_id, events, source_hash=source_hash)


def _identity_key(project_id: str, version_id: str, final_export_hash: str) -> str:
    if not project_id or not version_id or not final_export_hash:
        return ""
    return stable_hash({"project_id": project_id, "version_id": version_id, "final_export_hash": final_export_hash})


def _case_identity_key(case: dict[str, Any]) -> str:
    return _identity_key(str(case.get("project_id") or ""), str(case.get("version_id") or ""), str(case.get("final_export_hash") or ""))


def _renderer_release_ready(renderer: dict[str, Any]) -> bool:
    return renderer.get("runner_kind") == "real" and renderer.get("release_ready") is not False


def _read_optional_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return read_json(path)
    except (OSError, ValueError):
        return {}
    return {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        raise ReleaseAudioTimelineNotFoundError(f"Timeline event ledger not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _event_ledger_hash(events: list[dict[str, Any]]) -> str:
    return stable_hash(events)


def _readme(report: dict[str, Any], track_index: dict[str, Any], trend: dict[str, Any], risks: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
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


def _file_record(path: Path, root: Path, rel: str) -> dict[str, Any]:
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


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _semantic_hash(value: Any) -> str:
    return stable_hash(_strip_semantic_volatile(value))


def _strip_semantic_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_semantic_volatile(item) for key, item in value.items() if key not in {"generated_at", "integrity_hash"}}
    if isinstance(value, list):
        return [_strip_semantic_volatile(item) for item in value]
    return value
