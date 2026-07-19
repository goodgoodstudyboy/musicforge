# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, as_text as _as_text

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.quality.audio_encoding import AudioEncodingStore as AudioEncodingStore
from song_agent.domains.quality.audio_review_evidence import AudioReviewEvidenceStore as AudioReviewEvidenceStore, audio_review_summary_public as audio_review_summary_public
from song_agent.domains.delivery.distribution import DistributionStore as DistributionStore, distribution_signoff_summary as distribution_signoff_summary, distribution_target_summary as distribution_target_summary
from song_agent.domains.delivery.distribution_export import distribution_export_summary as distribution_export_summary, read_distribution_export_manifest as read_distribution_export_manifest
from song_agent.domains.delivery.distribution_verifier import distribution_verification_summary as distribution_verification_summary, verify_distribution_package as verify_distribution_package
from song_agent.domains.creation.encoded_audio_acceptance import EncodedAudioAcceptanceStore as EncodedAudioAcceptanceStore, encoded_audio_acceptance_summary_public as encoded_audio_acceptance_summary_public
from song_agent.domains.delivery.format_decisions import FormatDecisionStore as FormatDecisionStore, format_decision_export_summary as format_decision_export_summary
from song_agent.domains.quality.mastering_qa import MasteringStore as MasteringStore
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio import read_release_audio_qa as read_release_audio_qa, release_audio_summary as release_audio_summary
from song_agent.domains.delivery.release_export import read_release_export_manifest as read_release_export_manifest, release_export_summary as release_export_summary
from song_agent.domains.delivery.release_metadata import metadata_export_summary as metadata_export_summary, read_release_metadata as read_release_metadata, read_release_metadata_qa as read_release_metadata_qa, release_metadata_summary as release_metadata_summary
from song_agent.domains.delivery.release_metadata_qa import release_metadata_qa_summary as release_metadata_qa_summary
from song_agent.domains.delivery.release_qa import release_qa_summary as release_qa_summary, release_signoff_summary as release_signoff_summary
from song_agent.domains.delivery.release_verifier import verification_summary as verification_summary, verify_release_zip as verify_release_zip
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, release_document_source as release_document_source, release_summary as release_summary, stable_hash as stable_hash
from song_agent.domains.delivery.rights_clearance import RightsClearanceStore as RightsClearanceStore, rights_report_integrity_ok as rights_report_integrity_ok, rights_summary_hash as rights_summary_hash
from song_agent.domains.delivery.submission_evidence import SUBMITTED_OR_LATER as SUBMITTED_OR_LATER, SubmissionEvidenceStore as SubmissionEvidenceStore, submission_evidence_report_summary as submission_evidence_report_summary, submission_evidence_signoff_summary as submission_evidence_signoff_summary
from song_agent.domains.delivery.submission_evidence_verifier import submission_evidence_verification_summary as submission_evidence_verification_summary, verify_submission_evidence_package as verify_submission_evidence_package
from song_agent.domains.delivery.submission_export import read_submission_export_manifest as read_submission_export_manifest, submission_export_summary as submission_export_summary
from song_agent.domains.delivery.submission_verifier import submission_verification_summary as submission_verification_summary, verify_submission_package as verify_submission_package
from song_agent.domains.delivery.submissions import SubmissionStore as SubmissionStore, submission_batch_summary as submission_batch_summary, submission_signoff_summary as submission_signoff_summary
from song_agent.domains.trust.release_operations_contracts import OPERATIONS_BLOCKED_KEYS as OPERATIONS_BLOCKED_KEYS, REPORT_HASH_EXCLUDE_KEYS as REPORT_HASH_EXCLUDE_KEYS, operations_report_integrity_hash as operations_report_integrity_hash


OPERATIONS_SCHEMA_VERSION = 1
OPERATIONS_EXPORT_SCHEMA_VERSION = 1

OPERATIONS_STAGES = [
    "draft",
    "project_ready",
    "release_ready",
    "audio_ready",
    "metadata_ready",
    "rights_ready",
    "format_ready",
    "distribution_ready",
    "submission_ready",
    "submitted",
    "accepted",
    "archived",
]



class ReleaseOperationsError(ValueError):
    pass


class ReleaseOperationsStore:
    def __init__(
        self,
        *,
        release_store: ReleaseStore | None = None,
        project_store: ProjectStore | None = None,
        distribution_store: DistributionStore | None = None,
        submission_store: SubmissionStore | None = None,
        submission_evidence_store: SubmissionEvidenceStore | None = None,
        audio_review_store: AudioReviewEvidenceStore | None = None,
        mastering_store: MasteringStore | None = None,
        audio_encoding_store: AudioEncodingStore | None = None,
        encoded_audio_acceptance_store: EncodedAudioAcceptanceStore | None = None,
        format_decision_store: FormatDecisionStore | None = None,
        rights_clearance_store: RightsClearanceStore | None = None,
    ) -> None:
        self.release_store = release_store or ReleaseStore(project_store=project_store)
        self.project_store = project_store or self.release_store.project_store
        self.distribution_store = distribution_store or DistributionStore(self.release_store)
        self.submission_store = submission_store or SubmissionStore(self.release_store, self.distribution_store)
        self.submission_evidence_store = submission_evidence_store or SubmissionEvidenceStore(self.submission_store)
        self.audio_review_store = audio_review_store or AudioReviewEvidenceStore(self.release_store, self.project_store)
        self.mastering_store = mastering_store or MasteringStore(self.release_store, project_store=self.project_store)
        self.audio_encoding_store = audio_encoding_store or AudioEncodingStore(self.release_store, project_store=self.project_store)
        self.encoded_audio_acceptance_store = encoded_audio_acceptance_store or EncodedAudioAcceptanceStore(self.release_store, project_store=self.project_store, audio_encoding_store=self.audio_encoding_store)
        self.format_decision_store = format_decision_store or FormatDecisionStore(self.release_store, project_store=self.project_store, encoding_store=self.audio_encoding_store, distribution_store=self.distribution_store)
        self.rights_clearance_store = rights_clearance_store or RightsClearanceStore(self.release_store)
        self.lock = threading.RLock()

    def operations_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "operations"

    def report_path(self, release_id: str) -> Path:
        return self.operations_dir(release_id) / "operations-report.json"

    def export_dir(self, release_id: str) -> Path:
        return self.operations_dir(release_id) / "operations-export"

    def zip_path(self, release_id: str) -> Path:
        return self.operations_dir(release_id) / "release-operations-package.zip"

    def read_report(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.report_path(release_id)
        if not path.exists():
            return default if default is not None else {}
        data = read_json(path)
        return sanitize_metadata(_as_document(data), blocked_keys=OPERATIONS_BLOCKED_KEYS)

    def overview(self, release_id: str) -> DomainDocument:
        self.release_store.get_release(release_id)
        live_report = self.build_report(release_id, persist=False)
        stored = self.read_report(release_id, default={})
        stale = False
        integrity_ok = True
        if stored:
            stale = str(stored.get("source_hash") or "") != str(live_report.get("source_hash") or "")
            integrity_ok = operations_report_integrity_ok(stored)
            signoff_changed = stable_hash(stored.get("operations_signoff", {})) != stable_hash(live_report.get("operations_signoff", {}))
        report = stored or live_report
        if stored and (stale or signoff_changed):
            report = {**live_report, "stale": stale, "integrity_ok": operations_report_integrity_ok(live_report)}
        elif stored:
            report = {**stored, "stale": stale, "integrity_ok": integrity_ok}
        return sanitize_metadata(
            {
                "ok": True,
                "release_id": release_id,
                "summary": report.get("summary", {}),
                "report": report,
                "stale": stale,
                "integrity_ok": integrity_ok,
                "live_summary": live_report.get("summary", {}),
            },
            blocked_keys=OPERATIONS_BLOCKED_KEYS,
        )

    def refresh(self, release_id: str, *, now: str | None = None) -> DomainDocument:
        return self.build_report(release_id, persist=True, now=now)

    def build_report(self, release_id: str, *, persist: bool = False, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        release = self.release_store.get_release(release_id)
        collector = _OperationsCollector(self, release_id, now)
        domains, source, verifier_summaries, evidence_graph, package_summaries = collector.collect()
        stage_statuses = _stage_statuses(domains)
        current_stage, next_stage = _current_stage(stage_statuses)
        blockers = _renumber(_domain_items(domains, "blockers"), "blocker_id", "blk")
        warnings = _renumber(_domain_items(domains, "warnings"), "warning_id", "wrn")
        next_actions = _renumber(sorted(_domain_items(domains, "next_actions"), key=lambda item: int(item.get("priority", 100))), "action_id", "act")
        report_id = _next_report_id(self.operations_dir(release_id), existing=self.read_report(release_id, default={}).get("report_id"))
        source_hash = stable_hash(source)
        status = "failed" if blockers else "warning" if warnings else "passed"
        operations_signoff = _operations_signoff_summary_for_report(self, release_id, source_hash)
        stage_statuses = _apply_operations_signoff_stage(stage_statuses, operations_signoff)
        current_stage, next_stage = _current_stage(stage_statuses)
        redaction_summary = _redaction_summary({"domains": domains, "source": source, "graph": evidence_graph})
        if redaction_summary.get("status") == "failed":
            blockers.append(
                _blocker(
                    domain="operations",
                    scope="report",
                    entity_id=release_id,
                    check_id="operations_redaction_failed",
                    message="Operations report contains sensitive values.",
                    recommended_action="Remove sensitive values from source summaries and refresh Operations.",
                    action_hint="operations.refresh",
                    stage=current_stage,
                )
            )
            status = "failed"
        report = {
            "schema_version": OPERATIONS_SCHEMA_VERSION,
            "report_id": report_id,
            "release_id": release_id,
            "generated_at": now,
            "status": status,
            "current_stage": current_stage,
            "next_stage": next_stage,
            "source_hash": source_hash,
            "summary": {
                "release_name": release.name,
                "track_count": len(release.tracks),
                "distribution_target_count": len(source.get("distribution_targets", [])),
                "submission_batch_count": len(source.get("submission_batches", [])),
                "submission_evidence_count": sum(int(item.get("report_summary", {}).get("evidence_count") or 0) for item in source.get("submission_evidence", [])),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
                "next_action_count": len(next_actions),
                "package_summary_count": _package_summary_count(package_summaries),
                "operations_signoff": operations_signoff,
            },
            "stage_progress": _stage_progress(stage_statuses),
            "stage_statuses": stage_statuses,
            "domains": domains,
            "blockers": blockers,
            "warnings": warnings,
            "next_actions": next_actions,
            "evidence_graph": evidence_graph,
            "package_summaries": package_summaries,
            "verifier_summaries": verifier_summaries,
            "redaction_summary": redaction_summary,
            "source": source,
            "operations_signoff": operations_signoff,
        }
        report["integrity_hash"] = operations_report_integrity_hash(report)
        report = sanitize_metadata(report, blocked_keys=OPERATIONS_BLOCKED_KEYS)
        if persist:
            self.operations_dir(release_id).mkdir(parents=True, exist_ok=True)
            write_json(self.report_path(release_id), report)
        return report

    def report_is_stale(self, release_id: str, report: DomainDocument | None = None) -> bool:
        report = report or self.read_report(release_id, default={})
        if not report:
            return True
        current = self.build_report(release_id, persist=False)
        return str(report.get("source_hash") or "") != str(current.get("source_hash") or "")

    def export_operations(self, release_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            report = self.read_report(release_id, default={}) or self.refresh(release_id, now=now)
            if not operations_report_integrity_ok(report):
                raise ReleaseOperationsError("Operations Report integrity failed. Refresh before export.")
            export_dir = self.export_dir(release_id).resolve()
            release_dir = self.release_store.release_dir(release_id).resolve()
            _ensure_within(release_dir, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            readiness = {
                "release_id": release_id,
                "current_stage": report.get("current_stage"),
                "next_stage": report.get("next_stage"),
                "stage_progress": report.get("stage_progress", {}),
                "stage_statuses": report.get("stage_statuses", []),
                "blocker_count": report.get("summary", {}).get("blocker_count", 0),
                "warning_count": report.get("summary", {}).get("warning_count", 0),
            }
            verifier_summaries = _as_document(report.get("verifier_summaries"))
            _write_json(export_dir / "operations-report.json", report)
            _write_json(export_dir / "readiness-summary.json", readiness)
            _write_json(export_dir / "evidence-graph.json", report.get("evidence_graph", {}))
            _write_json(export_dir / "verifier-summaries.json", verifier_summaries)
            _write_readme(export_dir, report)
            files = [
                _file_record(export_dir, export_dir / "operations-report.json"),
                _file_record(export_dir, export_dir / "readiness-summary.json"),
                _file_record(export_dir, export_dir / "evidence-graph.json"),
                _file_record(export_dir, export_dir / "verifier-summaries.json"),
                _file_record(export_dir, export_dir / "README.txt"),
            ]
            manifest = {
                "schema_version": OPERATIONS_EXPORT_SCHEMA_VERSION,
                "tool": {"name": "MusicForge Release Operations Export", "version": __version__},
                "release_id": release_id,
                "generated_at": now,
                "source_hash": report.get("source_hash"),
                "report": {
                    "path": "operations-report.json",
                    "integrity_hash": report.get("integrity_hash"),
                    "report_hash": operations_report_integrity_hash(report),
                },
                "readiness": {
                    "path": "readiness-summary.json",
                    "sha256": _sha256(export_dir / "readiness-summary.json"),
                },
                "evidence_graph": {
                    "path": "evidence-graph.json",
                    "sha256": _sha256(export_dir / "evidence-graph.json"),
                },
                "verifier_summaries": {
                    "path": "verifier-summaries.json",
                    "sha256": _sha256(export_dir / "verifier-summaries.json"),
                },
                "summary": report.get("summary", {}),
                "package_summaries": report.get("package_summaries", {}),
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"report": report, "readiness": readiness, "verifier_summaries": verifier_summaries}),
            }
            _write_json(export_dir / "operations-manifest.json", manifest)
            return manifest

    def build_zip(self, release_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            export_dir = self.export_dir(release_id).resolve()
            release_dir = self.release_store.release_dir(release_id).resolve()
            zip_path = self.zip_path(release_id).resolve()
            _ensure_within(release_dir, export_dir)
            _ensure_within(release_dir, zip_path)
            if not (export_dir / "operations-manifest.json").exists():
                self.export_operations(release_id, now=now)
            manifest = self.read_export_manifest(release_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            _write_json(export_dir / "operations-manifest.json", manifest)
            entries = _zip_entries(export_dir)
            tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for resolved, entry in entries:
                        archive.write(resolved, entry)
                tmp_path.replace(zip_path)
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise
            return sanitize_metadata(
                {
                    "created_at": now,
                    "filename": zip_path.name,
                    "size_bytes": zip_path.stat().st_size,
                    "sha256": _sha256(zip_path),
                    "entry_count": len(entries),
                    "entries": [entry for _path, entry in entries],
                },
                blocked_keys=OPERATIONS_BLOCKED_KEYS,
            )

    def read_export_manifest(self, release_id: str) -> DomainDocument:
        path = self.export_dir(release_id) / "operations-manifest.json"
        if not path.exists():
            raise FileNotFoundError("Operations export has not been generated.")
        data = read_json(path)
        return sanitize_metadata(_as_document(data), blocked_keys=OPERATIONS_BLOCKED_KEYS)


from song_agent.domains.trust import v142_ro_readiness as _v142_ro_readiness
from song_agent.domains.trust.v142_ro_readiness import _OperationsCollector as _OperationsCollector, operations_report_integrity_ok as operations_report_integrity_ok, operations_report_summary as operations_report_summary, _domain as _domain, _finalize_domain as _finalize_domain, _add_blocker_action as _add_blocker_action, _add_warning_action as _add_warning_action, _blocker as _blocker
from song_agent.domains.trust import v142_ro_evidence as _v142_ro_evidence
from song_agent.domains.trust.v142_ro_evidence import _action_for_check as _action_for_check, _action_priority as _action_priority, _stage_statuses as _stage_statuses, _current_stage as _current_stage, _stage_progress as _stage_progress, _domain_items as _domain_items, _renumber as _renumber, _package_summary as _package_summary, _package_summary_count as _package_summary_count, _summary_status as _summary_status, _rights_summary as _rights_summary, _operations_signoff_summary_for_report as _operations_signoff_summary_for_report, _apply_operations_signoff_stage as _apply_operations_signoff_stage, _redaction_summary as _redaction_summary, _write_readme as _write_readme, _next_report_id as _next_report_id, _write_json as _write_json, _file_record as _file_record, _zip_entries as _zip_entries, _validate_relative_path as _validate_relative_path, _ensure_within as _ensure_within, _sha256 as _sha256

_v142_ro_readiness.bind_globals(globals())
_v142_ro_evidence.bind_globals(globals())
