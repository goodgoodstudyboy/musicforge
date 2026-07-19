# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

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

    def read_report(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.report_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseAudioCertificationNotFoundError(f"Release Audio Certification report not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def read_matrix(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.matrix_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseAudioCertificationNotFoundError(f"Release Audio Certification matrix not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def read_evidence_index(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.evidence_index_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseAudioCertificationNotFoundError(f"Release Audio Certification evidence index not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def read_blocker_register(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.blocker_register_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseAudioCertificationNotFoundError(f"Release Audio Certification blocker register not found: {release_id}.")
        return sanitize_metadata(read_json(path))

    def refresh_report(self, release_id: str) -> DomainDocument:
        with self.lock:
            if self.signoff_path(release_id).exists():
                raise ReleaseAudioCertificationStateError("Signed Release Audio Certification cannot be refreshed. Reset signoff before refreshing.")
            docs = self._build_documents(release_id)
            self._write_documents(release_id, docs)
            _append_event(self.events_path(release_id), "release_audio_certification_refreshed", {"release_id": release_id, "status": docs["report"].get("status"), "source_hash": docs["report"].get("source_hash")})
            return docs["report"]

    def signoff(self, release_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def export_package(self, release_id: str) -> DomainDocument:
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
            files: list[ImplementationDocument] = []

            def write_entry(rel: str, payload: DomainDocument | str) -> None:
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

    def build_zip(self, release_id: str) -> DomainDocument:
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

    def verify_zip(self, release_id: str, **kwargs: Any) -> DomainDocument:
        with self.lock:
            if self.signoff_path(release_id).exists():
                self._assert_signed_current(release_id)
            if not self.zip_path(release_id).exists():
                self.build_zip(release_id)
            report = verify_release_audio_certification_package(self.zip_path(release_id), **kwargs)
            write_release_audio_certification_verification_report(report, self.verification_report_path(release_id))
            return report

    def gate(self, release_id: str, *, required: bool, require_signed: bool = False) -> DomainDocument:
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
        campaign: ImplementationDocument = {}
        campaign_report: ImplementationDocument = {}
        case_index: ImplementationDocument = {}
        campaign_signoff: ImplementationDocument = {}
        governance_gate: ImplementationDocument = {}
        remediation_gate: ImplementationDocument = {}
        evidence_rows: list[ImplementationDocument] = []
        blockers: list[ImplementationDocument] = []
        warnings: list[ImplementationDocument] = []

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
    blockers: list[ImplementationDocument] = []
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


from song_agent.domains.quality import v142_rac_readiness as _v142_rac_readiness
from song_agent.domains.quality.v142_rac_readiness import _build_track_matrix as _build_track_matrix, _build_evidence_index as _build_evidence_index, _build_blocker_register as _build_blocker_register, _checks_from_matrix_and_evidence as _checks_from_matrix_and_evidence, _coverage as _coverage, _remediation_needed as _remediation_needed, _track_blockers as _track_blockers, _track_source as _track_source, _evidence as _evidence, _blocker as _blocker, _check as _check, _identity_key as _identity_key, _case_identity_key as _case_identity_key, _renderer_summary as _renderer_summary, _renderer_release_ready as _renderer_release_ready, _read_optional_json as _read_optional_json, _readme as _readme, _file_record as _file_record, _sha256_path as _sha256_path, _bounded as _bounded, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _semantic_hash as _semantic_hash, _strip_semantic_volatile as _strip_semantic_volatile, _append_event as _append_event, _blocker_message as _blocker_message

_v142_rac_readiness.bind_globals(globals())
