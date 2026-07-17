from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

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
from song_agent.domains.quality.release_audio_certification_verifier import RELEASE_AUDIO_CERTIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_CERTIFICATION_PACKAGE_TYPE, RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION as RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION, verify_release_audio_certification_package as verify_release_audio_certification_package, write_release_audio_certification_verification_report as write_release_audio_certification_verification_report
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash


class ReleaseAudioCertificationError(ValueError):
    pass


class ReleaseAudioCertificationNotFoundError(ReleaseAudioCertificationError):
    pass


class ReleaseAudioCertificationStateError(ReleaseAudioCertificationError):
    pass


class ReleaseAudioCertificationValidationError(ReleaseAudioCertificationError):
    pass


class ReleaseAudioCertificationStore:
    def __init__(
        self,
        *,
        release_store: ReleaseStore | None = None,
        project_store: ProjectStore | None = None,
        planner_store: AudioCampaignPlannerStore | None = None,
        campaign_store: AudioCampaignStore | None = None,
        governance_store: AudioCampaignGovernanceStore | None = None,
        remediation_store: AudioCampaignRemediationStore | None = None,
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
        self.lock = threading.RLock()

    def certification_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-certification"

    def report_path(self, release_id: str) -> Path:
        return self.certification_dir(release_id) / "certification-report.json"

    def matrix_path(self, release_id: str) -> Path:
        return self.certification_dir(release_id) / "track-audio-matrix.json"

    def evidence_index_path(self, release_id: str) -> Path:
        return self.certification_dir(release_id) / "evidence-index.json"

    def blocker_register_path(self, release_id: str) -> Path:
        return self.certification_dir(release_id) / "blocker-register.json"

    def signoff_path(self, release_id: str) -> Path:
        return self.certification_dir(release_id) / "certification-signoff.json"

    def verification_report_path(self, release_id: str) -> Path:
        return self.certification_dir(release_id) / "verification-report.json"

    def events_path(self, release_id: str) -> Path:
        return self.certification_dir(release_id) / "events.jsonl"

    def export_dir(self, release_id: str) -> Path:
        return self.certification_dir(release_id) / "export"

    def zip_path(self, release_id: str) -> Path:
        return self.certification_dir(release_id) / "release-audio-certification.zip"

    def read_report(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.report_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseAudioCertificationNotFoundError(f"Release Audio Certification report not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def read_matrix(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.matrix_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseAudioCertificationNotFoundError(f"Release Audio Certification matrix not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def read_evidence_index(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.evidence_index_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseAudioCertificationNotFoundError(f"Release Audio Certification evidence index not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def read_blocker_register(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.blocker_register_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseAudioCertificationNotFoundError(f"Release Audio Certification blocker register not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def refresh_report(self, release_id: str) -> dict[str, Any]:
        with self.lock:
            if self.signoff_path(release_id).exists():
                raise ReleaseAudioCertificationStateError("Signed Release Audio Certification cannot be refreshed. Reset signoff before refreshing.")
            docs = self._build_documents(release_id)
            self._write_documents(release_id, docs)
            _append_event(self.events_path(release_id), "release_audio_certification_refreshed", {"release_id": release_id, "status": docs["report"].get("status"), "source_hash": docs["report"].get("source_hash")})
            return docs["report"]

    def signoff(self, release_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            if self.signoff_path(release_id).exists():
                raise ReleaseAudioCertificationStateError("Release Audio Certification is already signed.")
            docs = self._build_documents(release_id)
            if docs["report"].get("status") != "passed":
                raise ReleaseAudioCertificationStateError("Release Audio Certification has blockers.")
            self._write_documents(release_id, docs)
            signoff = sanitize_metadata(
                {
                    "schema_version": RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION,
                    "signoff_id": f"racs-{release_id}",
                    "release_id": release_id,
                    "campaign_id": docs["report"].get("campaign_id"),
                    "status": "signed",
                    "signed_at": now_iso(),
                    "signed_by": _bounded(payload.get("signed_by") or payload.get("reviewer") or "audio-certification", 120),
                    "role": _bounded(payload.get("role") or "audio-certification-reviewer", 80),
                    "reason": _bounded(payload.get("reason") or "Release audio certification accepted.", 1000),
                    "source_hash": docs["report"].get("source_hash"),
                    "certification_report_hash": docs["report"].get("integrity_hash"),
                    "track_audio_matrix_hash": docs["matrix"].get("integrity_hash"),
                    "evidence_index_hash": docs["evidence"].get("integrity_hash"),
                    "blocker_register_hash": docs["blockers"].get("integrity_hash"),
                    "summary": docs["report"].get("summary", {}),
                }
            )
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(release_id), signoff)
            _append_event(self.events_path(release_id), "release_audio_certification_signed", {"release_id": release_id, "signoff_hash": signoff.get("integrity_hash")})
            return {"status": "signed", "signoff": signoff, "report": docs["report"]}

    def export_package(self, release_id: str) -> dict[str, Any]:
        with self.lock:
            if self.signoff_path(release_id).exists():
                snapshot = self._assert_signed_current(release_id)
                docs = {"report": snapshot["report"], "matrix": snapshot["matrix"], "evidence": snapshot["evidence"], "blockers": snapshot["blockers"]}
            else:
                docs = self._build_documents(release_id)
                self._write_documents(release_id, docs)
            export_dir = self.export_dir(release_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
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

            write_entry("certification-report.json", docs["report"])
            write_entry("track-audio-matrix.json", docs["matrix"])
            write_entry("evidence-index.json", docs["evidence"])
            write_entry("blocker-register.json", docs["blockers"])
            if self.signoff_path(release_id).exists():
                write_entry("certification-signoff.json", read_json(self.signoff_path(release_id)))
            write_entry("README.txt", _readme(docs["report"], docs["matrix"], docs["evidence"]))
            manifest = sanitize_metadata(
                {
                    "package_type": RELEASE_AUDIO_CERTIFICATION_PACKAGE_TYPE,
                    "schema_version": RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION,
                    "release_id": release_id,
                    "campaign_id": docs["report"].get("campaign_id"),
                    "generated_at": now_iso(),
                    "source_hash": docs["report"].get("source_hash"),
                    "report_hash": docs["report"].get("integrity_hash"),
                    "matrix_hash": docs["matrix"].get("integrity_hash"),
                    "evidence_index_hash": docs["evidence"].get("integrity_hash"),
                    "blocker_register_hash": docs["blockers"].get("integrity_hash"),
                    "signoff_hash": read_json(self.signoff_path(release_id)).get("integrity_hash") if self.signoff_path(release_id).exists() else None,
                    "summary": docs["report"].get("summary", {}),
                    "files": files,
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": docs["report"].get("status"), "export_dir": str(export_dir), "manifest": manifest}

    def build_zip(self, release_id: str) -> dict[str, Any]:
        with self.lock:
            if self.signoff_path(release_id).exists():
                self._assert_signed_current(release_id)
            exported = self.export_package(release_id)
            export_dir = self.export_dir(release_id)
            zip_path = self.zip_path(release_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        zf.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as zf:
                entries = sorted(item.filename for item in zf.infolist())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, export_dir, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        zf.write(path, path.relative_to(export_dir).as_posix())
            return {"status": exported.get("status"), "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_zip(self, release_id: str, **kwargs: Any) -> dict[str, Any]:
        with self.lock:
            if self.signoff_path(release_id).exists():
                self._assert_signed_current(release_id)
            if not self.zip_path(release_id).exists():
                self.build_zip(release_id)
            report = verify_release_audio_certification_package(self.zip_path(release_id), **kwargs)
            write_release_audio_certification_verification_report(report, self.verification_report_path(release_id))
            return report

    def gate(self, release_id: str, *, required: bool, require_signed: bool = False) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            signed = self.signoff_path(release_id).exists()
            if signed:
                snapshot = self._assert_signed_current(release_id)
                report = snapshot["report"]
                signoff = snapshot["signoff"]
            else:
                report = self.refresh_report(release_id)
                signoff = {}
            if report.get("status") != "passed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Certification has blockers.", "report": report}
            if require_signed and (not signoff or signoff.get("status") != "signed"):
                return {"status": "failed", "hard_block": True, "message": "Release Audio Certification signoff is missing.", "report": report}
            return {"status": "passed", "hard_block": False, "message": "Release Audio Certification gate passed.", "report": report, "signoff": signoff if signoff else None, "summary": report.get("summary", {})}
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(str(exc))}

    def _write_documents(self, release_id: str, docs: dict[str, ImplementationDocument]) -> None:
        write_json(self.report_path(release_id), docs["report"])
        write_json(self.matrix_path(release_id), docs["matrix"])
        write_json(self.evidence_index_path(release_id), docs["evidence"])
        write_json(self.blocker_register_path(release_id), docs["blockers"])

    def _assert_signed_current(self, release_id: str) -> ImplementationDocument:
        if not self.signoff_path(release_id).exists():
            raise ReleaseAudioCertificationStateError("Release Audio Certification signoff is missing.")
        signoff = read_json(self.signoff_path(release_id))
        report = self.read_report(release_id)
        matrix = self.read_matrix(release_id)
        evidence = self.read_evidence_index(release_id)
        blockers = self.read_blocker_register(release_id)
        if signoff.get("status") != "signed":
            raise ReleaseAudioCertificationStateError("Release Audio Certification signoff is not signed.")
        if not _integrity_ok(signoff) or not _integrity_ok(report) or not _integrity_ok(matrix) or not _integrity_ok(evidence) or not _integrity_ok(blockers):
            raise ReleaseAudioCertificationStateError("Release Audio Certification integrity failed.")
        if signoff.get("certification_report_hash") != report.get("integrity_hash"):
            raise ReleaseAudioCertificationStateError("Release Audio Certification report no longer matches signoff.")
        if signoff.get("track_audio_matrix_hash") != matrix.get("integrity_hash"):
            raise ReleaseAudioCertificationStateError("Release Audio Certification track matrix no longer matches signoff.")
        if signoff.get("evidence_index_hash") != evidence.get("integrity_hash"):
            raise ReleaseAudioCertificationStateError("Release Audio Certification evidence index no longer matches signoff.")
        if signoff.get("blocker_register_hash") != blockers.get("integrity_hash"):
            raise ReleaseAudioCertificationStateError("Release Audio Certification blocker register no longer matches signoff.")
        current = self._build_documents(release_id)
        if current["report"].get("source_hash") != report.get("source_hash") or current["report"].get("status") != report.get("status"):
            raise ReleaseAudioCertificationStateError("Release Audio Certification source is stale. Refresh and re-sign before using certification evidence.")
        if _semantic_hash(current["matrix"]) != _semantic_hash(matrix) or _semantic_hash(current["evidence"]) != _semantic_hash(evidence) or _semantic_hash(current["blockers"]) != _semantic_hash(blockers):
            raise ReleaseAudioCertificationStateError("Release Audio Certification documents are stale. Refresh and re-sign before using certification evidence.")
        return {"signoff": signoff, "report": report, "matrix": matrix, "evidence": evidence, "blockers": blockers}

    def _build_documents(self, release_id: str) -> dict[str, ImplementationDocument]:
        release = self.release_store.get_release(release_id)
        track_rows = [_track_row(self.project_store, track, release_id) for track in release.tracks]
        link = self.planner_store.read_link(release_id, default={})
        campaign_id = str(link.get("campaign_id") or "")
        campaign: dict[str, Any] = {}
        campaign_report: dict[str, Any] = {}
        case_index: dict[str, Any] = {}
        campaign_signoff: dict[str, Any] = {}
        governance_gate: dict[str, Any] = {}
        remediation_gate: dict[str, Any] = {}
        evidence_rows: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        if not track_rows:
            blockers.append(_blocker("release_tracks_missing", "Release has no tracks."))
        blockers.extend(_track_blockers(track_rows))

        if not campaign_id:
            blockers.append(_blocker("release_audio_campaign_link_missing", "Release Audio Campaign link is missing."))
        else:
            try:
                campaign = self.campaign_store.read_campaign(campaign_id)
                campaign_report = self.campaign_store.refresh_report(campaign_id)
                case_index = read_json(self.campaign_store.case_index_path(campaign_id))
                if self.campaign_store.signoff_path(campaign_id).exists():
                    campaign_signoff = read_json(self.campaign_store.signoff_path(campaign_id))
                evidence_rows.append(_evidence("audio_campaign", "campaign", campaign_id, campaign.get("status"), campaign.get("integrity_hash"), {"source_hash": campaign.get("source_hash")}))
                evidence_rows.append(_evidence("audio_campaign_report", "campaign_report", campaign_id, campaign_report.get("status"), campaign_report.get("integrity_hash"), {"source_hash": campaign_report.get("source_hash")}))
                evidence_rows.append(_evidence("audio_campaign_case_index", "case_index", campaign_id, "present", case_index.get("integrity_hash"), {"case_count": len(case_index.get("cases", []))}))
                if campaign_signoff:
                    evidence_rows.append(_evidence("audio_campaign_signoff", "signoff", campaign_id, campaign_signoff.get("status"), campaign_signoff.get("integrity_hash"), {"source_hash": campaign_signoff.get("source_hash")}))
                else:
                    blockers.append(_blocker("audio_campaign_signoff_missing", "Audio Campaign signoff is missing.", campaign_id=campaign_id))
                coverage = _coverage(track_rows, case_index.get("cases", []))
                if coverage.get("status") != "passed":
                    blockers.append(_blocker("audio_campaign_release_track_coverage", "Audio Campaign cases do not cover current Release tracks.", details=coverage))
                if campaign_report.get("status") != "passed":
                    blockers.append(_blocker("audio_campaign_report_not_passed", "Audio Campaign report is not passed.", campaign_id=campaign_id, status=campaign_report.get("status")))
                governance_gate = self.governance_store.gate(campaign_id, required=True)
                evidence_rows.append(
                    _evidence(
                        "audio_campaign_governance_archive",
                        "governance_archive",
                        campaign_id,
                        governance_gate.get("status"),
                        governance_gate.get("archive_verification_hash"),
                        {"archive_zip_sha256": governance_gate.get("archive_zip_sha256"), "campaign_report_hash": governance_gate.get("campaign_report_hash")},
                    )
                )
                if governance_gate.get("status") != "passed":
                    blockers.append(_blocker("audio_campaign_governance_archive_not_passed", "Audio Campaign governance archive gate failed.", campaign_id=campaign_id, details=governance_gate))
            except Exception as exc:
                blockers.append(_blocker("audio_campaign_evidence_unavailable", sanitize_sensitive_text(str(exc)), campaign_id=campaign_id))

        track_matrix = _build_track_matrix(release_id, campaign_id, track_rows, campaign, campaign_report, case_index)
        blockers.extend(track_matrix.get("blockers", []))
        remediation_needed = _remediation_needed(track_matrix, campaign_report)
        if remediation_needed:
            remediation_gate = self.remediation_store.gate(release_id, required=True, require_signed=True)
            evidence_rows.append(
                _evidence(
                    "audio_campaign_remediation",
                    "remediation",
                    release_id,
                    remediation_gate.get("status"),
                    (remediation_gate.get("signoff") or {}).get("integrity_hash") or (remediation_gate.get("closeout") or {}).get("integrity_hash"),
                    {"message": remediation_gate.get("message")},
                )
            )
            if remediation_gate.get("status") != "passed":
                blockers.append(_blocker("audio_campaign_remediation_not_passed", "Audio Campaign remediation is required but not passed.", release_id=release_id, details=remediation_gate))
        else:
            remediation_gate = {"status": "not_required", "hard_block": False, "needed": False}

        source = {
            "release_id": release_id,
            "track_identities_hash": stable_hash([_track_source(row) for row in track_rows]),
            "track_matrix_hash": stable_hash(track_matrix.get("tracks", [])),
            "link_hash": link.get("integrity_hash"),
            "campaign_id": campaign_id,
            "campaign_source_hash": campaign.get("source_hash"),
            "campaign_report_hash": campaign_report.get("integrity_hash"),
            "case_index_hash": case_index.get("integrity_hash"),
            "campaign_signoff_hash": campaign_signoff.get("integrity_hash"),
            "governance_gate_hash": stable_hash(governance_gate),
            "remediation_gate_hash": stable_hash(remediation_gate),
        }
        source["source_hash"] = stable_hash(source)
        status = "passed" if not blockers else "failed"
        track_matrix["source_hash"] = source["source_hash"]
        track_matrix["integrity_hash"] = _integrity_hash(track_matrix)
        evidence = _build_evidence_index(release_id, campaign_id, source, evidence_rows, remediation_needed, remediation_gate, governance_gate)
        blocker_register = _build_blocker_register(release_id, campaign_id, source, blockers, warnings)
        report = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION,
                "certification_id": f"racert-{release_id}",
                "release_id": release_id,
                "campaign_id": campaign_id or None,
                "status": status,
                "generated_at": now_iso(),
                "source": source,
                "summary": {
                    **track_matrix.get("summary", {}),
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                    "remediation_needed": remediation_needed,
                    "remediation_status": remediation_gate.get("status"),
                    "governance_status": governance_gate.get("status"),
                },
                "checks": _checks_from_matrix_and_evidence(track_matrix, evidence, blocker_register),
                "blockers": blockers,
                "warnings": warnings,
            }
        )
        report["source_hash"] = source["source_hash"]
        report["integrity_hash"] = _integrity_hash(report)
        return {"report": report, "matrix": track_matrix, "evidence": evidence, "blockers": blocker_register}


def _track_row(project_store: ProjectStore, track: Any, release_id: str) -> ImplementationDocument:
    project_id = str(getattr(track, "project_id", "") or "")
    project_dir = project_store.project_dir(project_id)
    export_dir = final_export_dir(project_dir)
    manifest_path = export_dir / "manifest.json"
    wav_path = export_dir / "song.wav"
    manifest = _read_optional_json(manifest_path)
    current_manifest_hash = _sha256_path(manifest_path) if manifest_path.exists() else None
    recorded_manifest_hash = str(getattr(track, "final_export_hash", "") or "")
    renderer = _renderer_summary(manifest)
    wav_sha = _sha256_path(wav_path) if wav_path.exists() else None
    blockers: list[dict[str, Any]] = []
    if not recorded_manifest_hash or not current_manifest_hash or recorded_manifest_hash != current_manifest_hash:
        blockers.append(_blocker("release_track_final_export_current", "Release track Final Export manifest is stale.", track_id=getattr(track, "track_id", None), expected_hash=recorded_manifest_hash, current_hash=current_manifest_hash))
    if not wav_path.exists() or wav_path.stat().st_size <= 44:
        blockers.append(_blocker("release_track_wav_present", "Release track WAV is missing.", track_id=getattr(track, "track_id", None)))
    if not _renderer_release_ready(renderer):
        blockers.append(_blocker("release_track_real_renderer", "Release track renderer evidence is not release-ready real audio.", track_id=getattr(track, "track_id", None), renderer=renderer))
    identity_key = _identity_key(project_id, str(getattr(track, "version_id", "") or ""), recorded_manifest_hash)
    return sanitize_metadata(
        {
            "track_id": getattr(track, "track_id", None),
            "release_id": release_id,
            "track_number": getattr(track, "track_number", None),
            "disc_number": getattr(track, "disc_number", None),
            "title": getattr(track, "title", None),
            "project_id": project_id,
            "version_id": getattr(track, "version_id", None),
            "final_export_hash": recorded_manifest_hash,
            "current_final_export_hash": current_manifest_hash,
            "final_export_current": bool(recorded_manifest_hash and current_manifest_hash and recorded_manifest_hash == current_manifest_hash),
            "identity_key": identity_key,
            "wav_sha256": wav_sha,
            "renderer": renderer,
            "real_audio": _renderer_release_ready(renderer),
            "test_fake": renderer.get("runner_kind") == "test_fake" or renderer.get("release_ready") is not True,
            "blockers": blockers,
        }
    )


def _build_track_matrix(release_id: str, campaign_id: str, track_rows: list[ImplementationDocument], campaign: ImplementationDocument, campaign_report: ImplementationDocument, case_index: ImplementationDocument) -> ImplementationDocument:
    case_by_key = {_case_identity_key(case): case for case in case_index.get("cases", []) if isinstance(case, dict) and _case_identity_key(case)}
    campaign_cases = _as_list(campaign.get("cases"))
    campaign_by_key = {_case_identity_key(case): case for case in campaign_cases if isinstance(case, dict) and _case_identity_key(case)}
    report_cases = _as_list(campaign_report.get("cases"))
    report_by_case_id = {str(case.get("case_id") or ""): case for case in report_cases if isinstance(case, dict)}
    tracks: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
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


def _build_evidence_index(release_id: str, campaign_id: str, source: ImplementationDocument, rows: list[ImplementationDocument], remediation_needed: bool, remediation_gate: ImplementationDocument, governance_gate: ImplementationDocument) -> ImplementationDocument:
    summary = {
        "evidence_count": len(rows),
        "campaign_id": campaign_id or None,
        "governance": {"status": governance_gate.get("status"), "archive_zip_sha256": governance_gate.get("archive_zip_sha256"), "verification_hash": governance_gate.get("archive_verification_hash")},
        "remediation": {"needed": remediation_needed, "status": remediation_gate.get("status"), "message": remediation_gate.get("message")},
    }
    evidence = sanitize_metadata({"schema_version": RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION, "release_id": release_id, "campaign_id": campaign_id or None, "generated_at": now_iso(), "source_hash": source.get("source_hash"), "summary": summary, "evidence": rows})
    evidence["integrity_hash"] = _integrity_hash(evidence)
    return evidence


def _build_blocker_register(release_id: str, campaign_id: str, source: ImplementationDocument, blockers: list[ImplementationDocument], warnings: list[ImplementationDocument]) -> ImplementationDocument:
    register = sanitize_metadata({"schema_version": RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION, "release_id": release_id, "campaign_id": campaign_id or None, "generated_at": now_iso(), "source_hash": source.get("source_hash"), "status": "passed" if not blockers else "failed", "summary": {"blocker_count": len(blockers), "warning_count": len(warnings)}, "blockers": blockers, "warnings": warnings})
    register["integrity_hash"] = _integrity_hash(register)
    return register


def _checks_from_matrix_and_evidence(matrix: ImplementationDocument, evidence: ImplementationDocument, blockers: ImplementationDocument) -> list[ImplementationDocument]:
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


def _coverage(track_rows: list[ImplementationDocument], cases: list[ImplementationDocument]) -> ImplementationDocument:
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


def _remediation_needed(matrix: ImplementationDocument, campaign_report: ImplementationDocument) -> bool:
    summary = _as_document(campaign_report.get("summary"))
    return any(
        int(summary.get(key) or 0) > 0
        for key in ("needs_fix_count", "rejected_count", "open_high_marker_count", "open_critical_marker_count", "failed_fix_sprint_count", "open_fix_sprint_count")
    ) or matrix.get("status") != "passed"


def _track_blockers(track_rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    for row in track_rows:
        rows.extend([dict(item) for item in row.get("blockers", []) if isinstance(item, dict)])
    return rows


def _track_source(row: ImplementationDocument) -> ImplementationDocument:
    return {
        "track_id": row.get("track_id"),
        "project_id": row.get("project_id"),
        "version_id": row.get("version_id"),
        "final_export_hash": row.get("final_export_hash"),
        "current_final_export_hash": row.get("current_final_export_hash"),
        "wav_sha256": row.get("wav_sha256"),
        "renderer": row.get("renderer"),
    }


def _evidence(evidence_id: str, kind: str, component_id: str, status: Any, integrity_hash: Any, details: ImplementationDocument | None = None) -> ImplementationDocument:
    return sanitize_metadata({"evidence_id": evidence_id, "kind": kind, "component_id": component_id, "status": status, "integrity_hash": integrity_hash, "details": details or {}})


def _blocker(check_id: str, message: str, **details: Any) -> ImplementationDocument:
    return sanitize_metadata({"check_id": check_id, "message": message, **details})


def _check(check_id: str, passed: bool, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message}


def _identity_key(project_id: str, version_id: str, final_export_hash: str) -> str:
    if not project_id or not version_id or not final_export_hash:
        return ""
    return stable_hash({"project_id": project_id, "version_id": version_id, "final_export_hash": final_export_hash})


def _case_identity_key(case: ImplementationDocument) -> str:
    return _identity_key(str(case.get("project_id") or ""), str(case.get("version_id") or ""), str(case.get("final_export_hash") or ""))


def _renderer_summary(manifest: ImplementationDocument) -> ImplementationDocument:
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


def _renderer_release_ready(renderer: ImplementationDocument) -> bool:
    return renderer.get("runner_kind") == "real" and renderer.get("release_ready") is not False


def _read_optional_json(path: Path) -> ImplementationDocument:
    try:
        if path.exists():
            return read_json(path)
    except (OSError, ValueError):
        return {}
    return {}


def _readme(report: ImplementationDocument, matrix: ImplementationDocument, evidence: ImplementationDocument) -> str:
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


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)


def _semantic_hash(value: Any) -> str:
    return stable_hash(_strip_semantic_volatile(value))


def _strip_semantic_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_semantic_volatile(item) for key, item in value.items() if key not in {"generated_at", "integrity_hash"}}
    if isinstance(value, list):
        return [_strip_semantic_volatile(item) for item in value]
    return value


def _append_event(path: Path, event_type: str, payload: ImplementationDocument) -> None:
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
