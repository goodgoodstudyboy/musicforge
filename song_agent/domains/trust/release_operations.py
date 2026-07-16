from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

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

    def read_report(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.report_path(release_id)
        if not path.exists():
            return default if default is not None else {}
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {}, blocked_keys=OPERATIONS_BLOCKED_KEYS)

    def overview(self, release_id: str) -> dict[str, Any]:
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

    def refresh(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        return self.build_report(release_id, persist=True, now=now)

    def build_report(self, release_id: str, *, persist: bool = False, now: str | None = None) -> dict[str, Any]:
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

    def report_is_stale(self, release_id: str, report: dict[str, Any] | None = None) -> bool:
        report = report or self.read_report(release_id, default={})
        if not report:
            return True
        current = self.build_report(release_id, persist=False)
        return str(report.get("source_hash") or "") != str(current.get("source_hash") or "")

    def export_operations(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
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
            verifier_summaries = report.get("verifier_summaries") if isinstance(report.get("verifier_summaries"), dict) else {}
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

    def build_zip(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
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

    def read_export_manifest(self, release_id: str) -> dict[str, Any]:
        path = self.export_dir(release_id) / "operations-manifest.json"
        if not path.exists():
            raise FileNotFoundError("Operations export has not been generated.")
        data = read_json(path)
        return sanitize_metadata(data if isinstance(data, dict) else {}, blocked_keys=OPERATIONS_BLOCKED_KEYS)


class _OperationsCollector:
    def __init__(self, store: ReleaseOperationsStore, release_id: str, now: str) -> None:
        self.store = store
        self.release_id = release_id
        self.now = now
        self.release = store.release_store.get_release(release_id)
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []

    def collect(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        release_domain, release_source, release_verifier, release_package = self._release_domain()
        metadata_domain, metadata_source = self._metadata_domain()
        audio_domain, audio_source = self._audio_domain()
        rights_domain, rights_source = self._rights_domain()
        format_domain, format_source = self._format_domain()
        distribution_domain, distribution_source, distribution_verifiers, distribution_packages = self._distribution_domain()
        submission_domain, submission_source, submission_verifiers, submission_packages = self._submission_domain()
        evidence_domain, evidence_source, evidence_verifiers, evidence_packages = self._submission_evidence_domain()
        domains = {
            "release": release_domain,
            "metadata": metadata_domain,
            "audio": audio_domain,
            "acceptance": self._optional_domain("acceptance", "missing", {"status": "not_collected"}, required=False),
            "rights": rights_domain,
            "format_decision": format_domain,
            "distribution": distribution_domain,
            "submission": submission_domain,
            "submission_evidence": evidence_domain,
            "exports": self._exports_domain(release_source, distribution_source, submission_source, evidence_source),
            "verifiers": self._verifiers_domain([release_verifier, *distribution_verifiers, *submission_verifiers, *evidence_verifiers]),
        }
        source = {
            "release": release_document_source(self.release),
            "release_signoff": release_source.get("signoff_summary", {}),
            "release_export_summary": release_source.get("export_summary", {}),
            "release_zip_summary": release_package,
            "metadata_summary": metadata_source,
            "acceptance_summary": {},
            "audio_summary": audio_source,
            "rights_summary": rights_source,
            "format_decision_summary": format_source,
            "distribution_targets": distribution_source,
            "submission_batches": submission_source,
            "submission_evidence": evidence_source,
            "verifier_summaries": [release_verifier, *distribution_verifiers, *submission_verifiers, *evidence_verifiers],
        }
        verifier_summaries = {
            "release": release_verifier,
            "distribution": distribution_verifiers,
            "submission": submission_verifiers,
            "submission_evidence": evidence_verifiers,
        }
        package_summaries = {
            "release_zip": release_package,
            "distribution_packages": distribution_packages,
            "submission_packages": submission_packages,
            "submission_evidence_packages": evidence_packages,
        }
        return (
            sanitize_metadata(domains, blocked_keys=OPERATIONS_BLOCKED_KEYS),
            sanitize_metadata(source, blocked_keys=OPERATIONS_BLOCKED_KEYS),
            sanitize_metadata(verifier_summaries, blocked_keys=OPERATIONS_BLOCKED_KEYS),
            {"nodes": self.nodes, "edges": self.edges},
            sanitize_metadata(package_summaries, blocked_keys=OPERATIONS_BLOCKED_KEYS),
        )

    def _release_domain(self) -> tuple[ImplementationDocument, ImplementationDocument, ImplementationDocument, ImplementationDocument]:
        qa = self.store.release_store.read_qa(self.release_id, default={})
        signoff = self.store.release_store.read_signoff(self.release_id, default={})
        try:
            manifest = read_release_export_manifest(self.store.release_store, self.release_id)
        except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
            manifest = {}
        summary = release_summary(self.release)
        qa_summary = release_qa_summary(qa)
        export_summary = release_export_summary(manifest)
        signoff_summary = release_signoff_summary(signoff)
        zip_path = self.store.release_store.zip_path(self.release_id)
        zip_summary = _package_summary(zip_path, status="exists" if zip_path.exists() else "missing")
        verifier_summary: dict[str, Any] = {"status": "missing"}
        if zip_path.exists():
            try:
                verifier_summary = verification_summary(verify_release_zip(zip_path))
            except Exception as exc:
                verifier_summary = {"status": "failed", "error": str(exc)}
        self._node(f"release:{self.release_id}", "release", self.release.name, signoff_summary.get("status") or self.release.status)
        checks = []
        checks.append(("release_tracks_exist", "passed" if self.release.tracks else "failed", "Release has at least one track."))
        checks.append(("release_qa_passed", "passed" if qa_summary.get("status") in {"passed", "warning"} else "failed", "Release QA is passed or warning."))
        checks.append(("release_export_exists", "passed" if export_summary.get("exists") else "failed", "Release Export exists."))
        checks.append(("release_zip_exists", "passed" if zip_path.exists() else "failed", "Release ZIP exists."))
        checks.append(("release_signoff_exists", "passed" if signoff_summary.get("status") in {"signed", "force_signed"} else "failed", "Release Signoff exists."))
        if zip_path.exists():
            checks.append(("release_zip_verify", "passed" if verifier_summary.get("status") in {"passed", "warning"} else "failed", "Release ZIP verifier passed."))
        domain = _domain("release", "passed", summary={**summary, "qa": qa_summary, "export": export_summary, "signoff": signoff_summary, "zip": zip_summary, "verifier": verifier_summary}, required=True)
        release_stage_by_check = {
            "release_tracks_exist": "project_ready",
            "release_qa_passed": "release_ready",
            "release_export_exists": "release_ready",
            "release_zip_exists": "release_ready",
            "release_signoff_exists": "release_ready",
            "release_zip_verify": "release_ready",
        }
        for check_id, status, message in checks:
            if status != "passed":
                _add_blocker_action(domain, self.release_id, check_id, message, _action_for_check(check_id), stage=release_stage_by_check.get(check_id, "release_ready"))
        _finalize_domain(domain)
        return domain, {"summary": summary, "qa_summary": qa_summary, "export_summary": export_summary, "signoff_summary": signoff_summary, "zip_summary": zip_summary}, verifier_summary, zip_summary

    def _metadata_domain(self) -> tuple[ImplementationDocument, ImplementationDocument]:
        metadata = read_release_metadata(self.store.release_store, self.release_id, default={})
        qa = read_release_metadata_qa(self.store.release_store, self.release_id, default={}) if metadata else {}
        try:
            manifest = read_release_export_manifest(self.store.release_store, self.release_id)
        except Exception:
            manifest = {}
        summary = release_metadata_summary(metadata, qa, metadata_export_summary(manifest))
        qa_summary = release_metadata_qa_summary(qa)
        export_summary = metadata_export_summary(manifest)
        required = bool(metadata)
        domain = _domain("metadata", "passed" if not required else "pending", summary={**summary, "qa": qa_summary, "export": export_summary}, required=required)
        if required and qa_summary.get("status") not in {"passed", "warning"}:
            _add_blocker_action(domain, self.release_id, "metadata_qa_missing_or_failed", "Release Metadata QA is missing or failed.", _action_for_check("metadata_qa_missing_or_failed"), stage="metadata_ready")
        if required and not export_summary.get("exists"):
            _add_blocker_action(domain, self.release_id, "metadata_export_missing", "Platform metadata export is missing.", _action_for_check("metadata_export_missing"), stage="metadata_ready")
        _finalize_domain(domain, optional_missing_pass=True)
        return domain, {"summary": summary, "qa_summary": qa_summary, "export_summary": export_summary}

    def _audio_domain(self) -> tuple[ImplementationDocument, ImplementationDocument]:
        audio_qa = read_release_audio_qa(self.store.release_store, self.release_id, default={})
        audio_reviews = self.store.audio_review_store.read_summary(self.release_id, default={})
        mastering = self.store.mastering_store.get_summary(self.release_id)
        encoded = self.store.audio_encoding_store.get_summary(self.release_id)
        encoded_acceptance = self.store.encoded_audio_acceptance_store.read_summary(self.release_id, default={})
        summary = {
            "audio_qa": release_audio_summary(audio_qa),
            "audio_reviews": audio_review_summary_public(audio_reviews),
            "mastering": _summary_status(mastering),
            "encoded_audio": _summary_status(encoded),
            "encoded_audio_acceptance": encoded_audio_acceptance_summary_public(encoded_acceptance),
        }
        required = any(bool(item) for item in (audio_qa, audio_reviews, mastering, encoded, encoded_acceptance))
        domain = _domain("audio", "passed" if not required else "pending", summary=summary, required=required)
        if audio_qa and summary["audio_qa"].get("status") not in {"passed", "warning"}:
            _add_blocker_action(domain, self.release_id, "audio_health_failed", "Release Audio QA is failed or stale.", _action_for_check("audio_health_failed"), stage="audio_ready")
        if audio_reviews and summary["audio_reviews"].get("status") not in {"passed", "warning"}:
            _add_blocker_action(domain, self.release_id, "audio_review_missing", "Per-track manual audio review is incomplete.", _action_for_check("audio_review_missing"), stage="audio_ready")
        if mastering and summary["mastering"].get("status") not in {"passed", "warning", "selected"}:
            _add_warning_action(domain, self.release_id, "mastering_not_ready", "Mastering QA is not ready.", _action_for_check("mastering_not_ready"), stage="audio_ready")
        if encoded and summary["encoded_audio"].get("status") not in {"passed", "warning"}:
            _add_warning_action(domain, self.release_id, "encoded_audio_not_ready", "Encoded audio summary is not ready.", _action_for_check("encoded_audio_not_ready"), stage="audio_ready")
        if encoded_acceptance and summary["encoded_audio_acceptance"].get("status") not in {"passed", "warning"}:
            _add_warning_action(domain, self.release_id, "encoded_review_missing", "Encoded audio review evidence is incomplete.", _action_for_check("encoded_review_missing"), stage="audio_ready")
        _finalize_domain(domain, optional_missing_pass=True)
        return domain, summary

    def _rights_domain(self) -> tuple[ImplementationDocument, ImplementationDocument]:
        try:
            report = self.store.rights_clearance_store.read_report(self.release_id, default={})
        except TypeError:
            report = {}
        except Exception:
            report = {}
        summary = _rights_summary(report)
        required = bool(report)
        domain = _domain("rights", "passed" if not required else "pending", summary=summary, required=required)
        if required and (summary.get("status") not in {"passed", "warning"} or not rights_report_integrity_ok(report)):
            _add_blocker_action(domain, self.release_id, "rights_clearance_failed", "Rights Clearance is failed, stale, or tampered.", _action_for_check("rights_clearance_failed"), stage="rights_ready")
        _finalize_domain(domain, optional_missing_pass=True)
        return domain, summary

    def _format_domain(self) -> tuple[ImplementationDocument, ImplementationDocument]:
        try:
            report = self.store.format_decision_store.active_report(self.release_id)
        except Exception:
            report = {}
        matrix = {}
        try:
            if report:
                matrix = self.store.format_decision_store.read_matrix(self.release_id, str(report.get("session_id") or ""))
        except Exception:
            matrix = {}
        summary = format_decision_export_summary(report, matrix if isinstance(matrix, dict) else None) if report else {"status": "missing"}
        required = bool(report)
        domain = _domain("format_decision", "passed" if not required else "pending", summary=summary, required=required)
        if required and summary.get("status") not in {"passed", "warning", "selected"}:
            _add_blocker_action(domain, self.release_id, "format_decision_failed", "Format Decision is missing or failed.", _action_for_check("format_decision_failed"), stage="format_ready")
        _finalize_domain(domain, optional_missing_pass=True)
        return domain, summary

    def _distribution_domain(self) -> tuple[ImplementationDocument, list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
        targets = self.store.distribution_store.list_targets(self.release_id)
        rows: list[dict[str, Any]] = []
        verifiers: list[dict[str, Any]] = []
        packages: list[dict[str, Any]] = []
        domain = _domain("distribution", "passed" if not targets else "pending", summary={"target_count": len(targets)}, required=bool(targets))
        for target in targets:
            target_summary = distribution_target_summary(target)
            qa = self.store.distribution_store.read_qa(self.release_id, target.target_id, default={})
            signoff = self.store.distribution_store.read_signoff(self.release_id, target, default={})
            package_id = self.store.distribution_store.latest_package_id(target)
            manifest = {}
            if package_id:
                try:
                    manifest = read_distribution_export_manifest(self.store.distribution_store, self.release_id, package_id)
                except Exception:
                    manifest = {}
            export_summary = distribution_export_summary(manifest)
            zip_path = self.store.distribution_store.package_zip_path(self.release_id, package_id) if package_id else Path("")
            package_summary = _package_summary(zip_path, status="exists" if package_id and zip_path.exists() else "missing")
            verifier_summary: dict[str, Any] = {"status": "missing", "target_id": target.target_id, "package_id": package_id}
            if package_id and zip_path.exists():
                try:
                    verifier_summary = distribution_verification_summary(verify_distribution_package(zip_path))
                except Exception as exc:
                    verifier_summary = {"status": "failed", "target_id": target.target_id, "package_id": package_id, "error": str(exc)}
            verifiers.append(verifier_summary)
            packages.append({**package_summary, "target_id": target.target_id, "package_id": package_id, "verify_status": verifier_summary.get("status")})
            row = {"target": target_summary, "qa_summary": _summary_status(qa), "export_summary": export_summary, "signoff_summary": distribution_signoff_summary(signoff), "package_summary": package_summary, "verifier_summary": verifier_summary}
            rows.append(row)
            self._node(f"distribution:{target.target_id}", "distribution_target", target.name, row["signoff_summary"].get("status") or target.status)
            self._edge(f"release:{self.release_id}", f"distribution:{target.target_id}", "packages")
            if row["qa_summary"].get("status") not in {"passed", "warning"}:
                _add_blocker_action(domain, target.target_id, "distribution_qa_missing", f"Distribution QA is not ready for {target.target_id}.", _action_for_check("distribution_qa_missing"), stage="distribution_ready")
            if not export_summary.get("exists"):
                _add_blocker_action(domain, target.target_id, "distribution_export_missing", f"Distribution Export is missing for {target.target_id}.", _action_for_check("distribution_export_missing"), stage="distribution_ready")
            if not (package_id and zip_path.exists()):
                _add_blocker_action(domain, target.target_id, "distribution_zip_missing", f"Distribution ZIP is missing for {target.target_id}.", _action_for_check("distribution_zip_missing"), stage="distribution_ready")
            if row["signoff_summary"].get("status") not in {"signed", "force_signed"}:
                _add_blocker_action(domain, target.target_id, "distribution_signoff_missing", f"Distribution Signoff is missing for {target.target_id}.", _action_for_check("distribution_signoff_missing"), stage="distribution_ready")
            if zip_path and zip_path.exists() and verifier_summary.get("status") not in {"passed", "warning"}:
                _add_blocker_action(domain, target.target_id, "distribution_verify_failed", f"Distribution verifier failed for {target.target_id}.", _action_for_check("distribution_verify_failed"), stage="distribution_ready")
        domain["summary"] = {**domain["summary"], "signed_target_count": sum(1 for row in rows if row["signoff_summary"].get("status") in {"signed", "force_signed"})}
        _finalize_domain(domain, optional_missing_pass=True)
        return domain, rows, verifiers, packages

    def _submission_domain(self) -> tuple[ImplementationDocument, list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
        batches = self.store.submission_store.list_submissions(self.release_id)
        rows: list[dict[str, Any]] = []
        verifiers: list[dict[str, Any]] = []
        packages: list[dict[str, Any]] = []
        domain = _domain("submission", "passed" if not batches else "pending", summary={"submission_count": len(batches)}, required=bool(batches))
        for batch in batches:
            batch_summary = submission_batch_summary(batch)
            qa = self.store.submission_store.read_qa(self.release_id, batch.submission_id, default={})
            signoff = self.store.submission_store.read_signoff(self.release_id, batch.submission_id, default={})
            try:
                manifest = read_submission_export_manifest(self.store.submission_store, self.release_id, batch.submission_id)
            except Exception:
                manifest = {}
            export_summary = submission_export_summary(manifest)
            zip_path = self.store.submission_store.package_zip_path(self.release_id, batch.submission_id)
            package_summary = _package_summary(zip_path, status="exists" if zip_path.exists() else "missing")
            verifier_summary: dict[str, Any] = {"status": "missing", "submission_id": batch.submission_id}
            if zip_path.exists():
                try:
                    verifier_summary = submission_verification_summary(verify_submission_package(zip_path))
                except Exception as exc:
                    verifier_summary = {"status": "failed", "submission_id": batch.submission_id, "error": str(exc)}
            verifiers.append(verifier_summary)
            packages.append({**package_summary, "submission_id": batch.submission_id, "verify_status": verifier_summary.get("status")})
            row = {"submission": batch_summary, "qa_summary": _summary_status(qa), "export_summary": export_summary, "signoff_summary": submission_signoff_summary(signoff), "package_summary": package_summary, "verifier_summary": verifier_summary, "items": [item.to_dict() for item in batch.items]}
            rows.append(row)
            self._node(f"submission:{batch.submission_id}", "submission_batch", batch.name, row["signoff_summary"].get("status") or batch.status)
            self._edge(f"release:{self.release_id}", f"submission:{batch.submission_id}", "submits")
            if row["qa_summary"].get("status") not in {"passed", "warning"}:
                _add_blocker_action(domain, batch.submission_id, "submission_qa_missing", f"Submission QA is not ready for {batch.submission_id}.", _action_for_check("submission_qa_missing"), stage="submission_ready")
            if not export_summary.get("exists"):
                _add_blocker_action(domain, batch.submission_id, "submission_export_missing", f"Submission Export is missing for {batch.submission_id}.", _action_for_check("submission_export_missing"), stage="submission_ready")
            if not zip_path.exists():
                _add_blocker_action(domain, batch.submission_id, "submission_zip_missing", f"Submission ZIP is missing for {batch.submission_id}.", _action_for_check("submission_zip_missing"), stage="submission_ready")
            if row["signoff_summary"].get("status") not in {"signed", "force_signed"}:
                _add_blocker_action(domain, batch.submission_id, "submission_signoff_missing", f"Submission Signoff is missing for {batch.submission_id}.", _action_for_check("submission_signoff_missing"), stage="submission_ready")
            if zip_path.exists() and verifier_summary.get("status") not in {"passed", "warning"}:
                _add_blocker_action(domain, batch.submission_id, "submission_verify_failed", f"Submission verifier failed for {batch.submission_id}.", _action_for_check("submission_verify_failed"), stage="submission_ready")
            pending = [item.item_id for item in batch.items if item.status not in SUBMITTED_OR_LATER]
            if pending:
                _add_blocker_action(domain, batch.submission_id, "submission_item_not_submitted", f"Submission items not submitted: {', '.join(pending[:5])}.", _action_for_check("submission_item_not_submitted"), stage="submitted")
        domain["summary"] = {**domain["summary"], "signed_count": sum(1 for row in rows if row["signoff_summary"].get("status") in {"signed", "force_signed"}), "submitted_or_later_count": sum(sum(1 for item in row["items"] if item.get("status") in SUBMITTED_OR_LATER) for row in rows)}
        _finalize_domain(domain, optional_missing_pass=True)
        return domain, rows, verifiers, packages

    def _submission_evidence_domain(self) -> tuple[ImplementationDocument, list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
        batches = self.store.submission_store.list_submissions(self.release_id)
        rows: list[dict[str, Any]] = []
        verifiers: list[dict[str, Any]] = []
        packages: list[dict[str, Any]] = []
        domain = _domain("submission_evidence", "passed" if not batches else "pending", summary={"submission_count": len(batches)}, required=bool(batches))
        for batch in batches:
            report = self.store.submission_evidence_store.read_report(self.release_id, batch.submission_id, default={})
            signoff = self.store.submission_evidence_store.read_signoff(self.release_id, batch.submission_id, default={})
            try:
                manifest = self.store.submission_evidence_store.read_export_manifest(self.release_id, batch.submission_id)
            except Exception:
                manifest = {}
            zip_path = self.store.submission_evidence_store.package_zip_path(self.release_id, batch.submission_id)
            verifier_summary: dict[str, Any] = {"status": "missing", "submission_id": batch.submission_id}
            if zip_path.exists():
                try:
                    verifier_summary = submission_evidence_verification_summary(verify_submission_evidence_package(zip_path, require_submitted=True, require_accepted=True))
                except Exception as exc:
                    verifier_summary = {"status": "failed", "submission_id": batch.submission_id, "error": str(exc)}
            report_summary = submission_evidence_report_summary(report)
            signoff_summary = submission_evidence_signoff_summary(signoff)
            export_summary = {"status": "exported" if manifest else "missing", "exists": bool(manifest), "source_hash": manifest.get("source_hash"), "file_count": len(manifest.get("files", [])) if isinstance(manifest.get("files"), list) else 0}
            package_summary = _package_summary(zip_path, status="exists" if zip_path.exists() else "missing")
            rows.append({"submission_id": batch.submission_id, "report_summary": report_summary, "signoff_summary": signoff_summary, "export_summary": export_summary, "package_summary": package_summary, "verifier_summary": verifier_summary})
            verifiers.append(verifier_summary)
            packages.append({**package_summary, "submission_id": batch.submission_id, "verify_status": verifier_summary.get("status")})
            self._node(f"submission_evidence:{batch.submission_id}", "submission_evidence", f"Evidence {batch.submission_id}", signoff_summary.get("status") or report_summary.get("status"))
            self._edge(f"submission:{batch.submission_id}", f"submission_evidence:{batch.submission_id}", "evidence")
            if report_summary.get("status") not in {"passed", "warning"}:
                _add_blocker_action(domain, batch.submission_id, "submission_evidence_report_missing", f"Submission Evidence report is missing or failed for {batch.submission_id}.", _action_for_check("submission_evidence_report_missing"), stage="accepted")
            if report_summary.get("accepted_count", 0) < report_summary.get("item_count", 0):
                _add_blocker_action(domain, batch.submission_id, "submission_evidence_acceptance_missing", f"Submission Evidence accepted records are incomplete for {batch.submission_id}.", _action_for_check("submission_evidence_acceptance_missing"), stage="accepted")
            if not export_summary.get("exists"):
                _add_blocker_action(domain, batch.submission_id, "submission_evidence_export_missing", f"Submission Evidence export is missing for {batch.submission_id}.", _action_for_check("submission_evidence_export_missing"), stage="accepted")
            if not zip_path.exists():
                _add_blocker_action(domain, batch.submission_id, "submission_evidence_zip_missing", f"Submission Evidence ZIP is missing for {batch.submission_id}.", _action_for_check("submission_evidence_zip_missing"), stage="accepted")
            if signoff_summary.get("status") not in {"signed", "force_signed"}:
                _add_blocker_action(domain, batch.submission_id, "submission_evidence_signoff_missing", f"Submission Evidence signoff is missing for {batch.submission_id}.", _action_for_check("submission_evidence_signoff_missing"), stage="accepted")
            if zip_path.exists() and verifier_summary.get("status") not in {"passed", "warning"}:
                _add_blocker_action(domain, batch.submission_id, "submission_evidence_verify_failed", f"Submission Evidence verifier failed for {batch.submission_id}.", _action_for_check("submission_evidence_verify_failed"), stage="accepted")
        domain["summary"] = {**domain["summary"], "signed_count": sum(1 for row in rows if row["signoff_summary"].get("status") in {"signed", "force_signed"}), "accepted_count": sum(int(row["report_summary"].get("accepted_count") or 0) for row in rows)}
        _finalize_domain(domain, optional_missing_pass=True)
        return domain, rows, verifiers, packages

    def _exports_domain(self, release_source: ImplementationDocument, distribution_source: list[ImplementationDocument], submission_source: list[ImplementationDocument], evidence_source: list[ImplementationDocument]) -> ImplementationDocument:
        missing = []
        if not release_source.get("export_summary", {}).get("exists"):
            missing.append("release")
        missing.extend(f"distribution:{row.get('target', {}).get('target_id')}" for row in distribution_source if not row.get("export_summary", {}).get("exists"))
        missing.extend(f"submission:{row.get('submission', {}).get('submission_id')}" for row in submission_source if not row.get("export_summary", {}).get("exists"))
        missing.extend(f"submission_evidence:{row.get('submission_id')}" for row in evidence_source if not row.get("export_summary", {}).get("exists"))
        domain = _domain("exports", "passed", summary={"missing_exports": missing, "missing_count": len(missing)}, required=False)
        for item in missing:
            _add_warning_action(domain, item, "export_missing", f"Export missing: {item}.", {"action_type": "export", "label": "Build missing export", "api_hint": ""}, stage="release_ready")
        _finalize_domain(domain, optional_missing_pass=True)
        return domain

    def _verifiers_domain(self, summaries: list[ImplementationDocument]) -> ImplementationDocument:
        failed = [item for item in summaries if item.get("status") not in {"passed", "warning", "missing"}]
        domain = _domain("verifiers", "passed", summary={"verifier_count": len(summaries), "failed_count": len(failed)}, required=False)
        for item in failed:
            _add_blocker_action(domain, str(item.get("release_id") or item.get("target_id") or item.get("submission_id") or "package"), "package_verifier_failed", "A package verifier failed.", _action_for_check("package_verifier_failed"), stage="release_ready")
        _finalize_domain(domain, optional_missing_pass=True)
        return domain

    def _optional_domain(self, domain_id: str, status: str, summary: ImplementationDocument, *, required: bool) -> ImplementationDocument:
        domain = _domain(domain_id, status, summary=summary, required=required)
        _finalize_domain(domain, optional_missing_pass=True)
        return domain

    def _node(self, node_id: str, node_type: str, label: str, status: str) -> None:
        self.nodes.append({"id": node_id, "type": node_type, "label": sanitize_sensitive_text(label), "status": status or "missing"})

    def _edge(self, source: str, target: str, relation: str) -> None:
        self.edges.append({"from": source, "to": target, "relation": relation})





def operations_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == operations_report_integrity_hash(data)


def operations_report_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "report_id": data.get("report_id"),
            "release_id": data.get("release_id"),
            "current_stage": data.get("current_stage") or "draft",
            "next_stage": data.get("next_stage"),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "next_action_count": summary.get("next_action_count", 0),
            "source_hash": data.get("source_hash"),
            "integrity_ok": operations_report_integrity_ok(data),
        },
        blocked_keys=OPERATIONS_BLOCKED_KEYS,
    )


def _domain(domain_id: str, status: str, *, summary: ImplementationDocument, required: bool) -> ImplementationDocument:
    return {"status": status, "summary": summary, "required": required, "stale": False, "blocker_count": 0, "warning_count": 0, "blockers": [], "warnings": [], "next_actions": [], "source_hash": stable_hash(summary)}


def _finalize_domain(domain: ImplementationDocument, *, optional_missing_pass: bool = False) -> None:
    blockers = domain.get("blockers") if isinstance(domain.get("blockers"), list) else []
    warnings = domain.get("warnings") if isinstance(domain.get("warnings"), list) else []
    domain["blocker_count"] = len(blockers)
    domain["warning_count"] = len(warnings)
    if blockers:
        domain["status"] = "failed"
    elif warnings:
        domain["status"] = "warning"
    elif optional_missing_pass and not domain.get("required"):
        domain["status"] = "not_required"
    else:
        domain["status"] = "passed"
    domain["source_hash"] = stable_hash(domain.get("summary", {}))


def _add_blocker_action(domain: ImplementationDocument, entity_id: str, check_id: str, message: str, action: ImplementationDocument, *, stage: str) -> None:
    blocker = _blocker(domain=action.get("domain") or "release", scope=action.get("scope") or action.get("domain") or "release", entity_id=entity_id, check_id=check_id, message=message, recommended_action=action.get("description") or action.get("label") or "", action_hint=action.get("action_type") or "", stage=stage)
    domain.setdefault("blockers", []).append(blocker)
    domain.setdefault("next_actions", []).append({**action, "entity_id": entity_id, "unblocks": [stage], "blocked_by": [check_id]})


def _add_warning_action(domain: ImplementationDocument, entity_id: str, check_id: str, message: str, action: ImplementationDocument, *, stage: str) -> None:
    warning = {"domain": action.get("domain") or "release", "scope": action.get("scope") or action.get("domain") or "release", "entity_id": entity_id, "check_id": check_id, "severity": "warning", "message": message, "recommended_action": action.get("description") or action.get("label") or "", "action_hint": action.get("action_type") or "", "stage": stage}
    domain.setdefault("warnings", []).append(sanitize_metadata(warning, blocked_keys=OPERATIONS_BLOCKED_KEYS))
    domain.setdefault("next_actions", []).append({**action, "entity_id": entity_id, "unblocks": [stage], "blocked_by": [check_id]})


def _blocker(*, domain: str, scope: str, entity_id: str, check_id: str, message: str, recommended_action: str, action_hint: str, stage: str) -> ImplementationDocument:
    return sanitize_metadata({"domain": domain, "scope": scope, "entity_id": entity_id, "check_id": check_id, "severity": "blocking", "message": message, "recommended_action": recommended_action, "action_hint": action_hint, "stage": stage}, blocked_keys=OPERATIONS_BLOCKED_KEYS)


def _action_for_check(check_id: str) -> ImplementationDocument:
    mapping = {
        "release_tracks_exist": ("release", "release.add_track", "Add Release Track", "Add at least one signed project to the release."),
        "release_qa_passed": ("release", "release.qa.refresh", "Refresh Release QA", "Refresh Release QA and fix blockers."),
        "release_export_exists": ("release", "release.export", "Build Release Export", "Build the Release Export bundle."),
        "release_zip_exists": ("release", "release.zip", "Build Release ZIP", "Build the Release ZIP."),
        "release_signoff_exists": ("release", "release.signoff", "Sign Release", "Sign the Release after QA and export are current."),
        "release_zip_verify": ("release", "release.verify", "Verify Release ZIP", "Run the Release ZIP verifier."),
        "metadata_qa_missing_or_failed": ("metadata", "metadata.qa.refresh", "Refresh Metadata QA", "Refresh Metadata QA and fix required fields."),
        "metadata_export_missing": ("metadata", "metadata.export", "Export Metadata", "Export platform metadata files."),
        "audio_health_failed": ("audio", "audio.render_or_health", "Refresh Audio QA", "Render audio or refresh Release Audio QA."),
        "audio_review_missing": ("audio", "audio.review", "Complete Audio Review", "Complete current per-track manual audio reviews."),
        "mastering_not_ready": ("audio", "mastering.select", "Complete Mastering", "Select and review a mastered candidate."),
        "encoded_audio_not_ready": ("audio", "encoded.render", "Render Encoded Audio", "Render required encoded audio formats."),
        "encoded_review_missing": ("audio", "encoded.review", "Review Encoded Audio", "Complete encoded format listening reviews."),
        "rights_clearance_failed": ("rights", "rights.refresh", "Refresh Rights Clearance", "Fix rights clearance and refresh the report."),
        "format_decision_failed": ("format_decision", "format_decision.refresh", "Complete Format Decision", "Create or refresh a format decision report."),
        "distribution_qa_missing": ("distribution", "distribution.qa.refresh", "Refresh Distribution QA", "Refresh target QA."),
        "distribution_export_missing": ("distribution", "distribution.export", "Build Distribution Export", "Build target export."),
        "distribution_zip_missing": ("distribution", "distribution.zip", "Build Distribution ZIP", "Build target ZIP."),
        "distribution_signoff_missing": ("distribution", "distribution.signoff", "Sign Distribution", "Sign target package."),
        "distribution_verify_failed": ("distribution", "distribution.verify", "Verify Distribution", "Run distribution verifier."),
        "submission_qa_missing": ("submission", "submission.qa.refresh", "Refresh Submission QA", "Refresh submission QA."),
        "submission_export_missing": ("submission", "submission.export", "Build Submission Export", "Build submission export."),
        "submission_zip_missing": ("submission", "submission.zip", "Build Submission ZIP", "Build submission ZIP."),
        "submission_signoff_missing": ("submission", "submission.signoff", "Sign Submission", "Sign submission package."),
        "submission_verify_failed": ("submission", "submission.verify", "Verify Submission", "Run submission verifier."),
        "submission_item_not_submitted": ("submission", "submission.record_receipt", "Record Submission Receipt", "Record submitted-or-later evidence for each submission item."),
        "submission_evidence_report_missing": ("submission_evidence", "submission_evidence.report.refresh", "Refresh Evidence Report", "Refresh submission evidence report."),
        "submission_evidence_acceptance_missing": ("submission_evidence", "submission_evidence.acceptance", "Record Acceptance Evidence", "Record platform acceptance evidence."),
        "submission_evidence_export_missing": ("submission_evidence", "submission_evidence.export", "Build Evidence Export", "Build submission evidence export."),
        "submission_evidence_zip_missing": ("submission_evidence", "submission_evidence.zip", "Build Evidence ZIP", "Build submission evidence ZIP."),
        "submission_evidence_signoff_missing": ("submission_evidence", "submission_evidence.signoff", "Sign Evidence", "Sign submission evidence archive."),
        "submission_evidence_verify_failed": ("submission_evidence", "submission_evidence.verify", "Verify Evidence", "Run submission evidence verifier."),
        "package_verifier_failed": ("verifiers", "package.verify", "Verify Package", "Run the relevant package verifier and fix blockers."),
    }
    domain, action_type, label, description = mapping.get(check_id, ("operations", "operations.refresh", "Refresh Operations", "Refresh the Operations report."))
    return {"priority": _action_priority(action_type), "domain": domain, "scope": domain, "action_type": action_type, "label": label, "description": description, "api_hint": ""}


def _action_priority(action_type: str) -> int:
    order = ["release.add_track", "release.qa.refresh", "release.export", "release.zip", "release.signoff", "distribution.qa.refresh", "distribution.export", "distribution.zip", "distribution.signoff", "submission.qa.refresh", "submission.export", "submission.zip", "submission.signoff", "submission.record_receipt", "submission_evidence.report.refresh", "submission_evidence.acceptance", "submission_evidence.export", "submission_evidence.zip", "submission_evidence.signoff"]
    try:
        return order.index(action_type) + 1
    except ValueError:
        return 100


def _stage_statuses(domains: ImplementationDocument) -> list[ImplementationDocument]:
    blockers_by_stage: dict[str, list[dict[str, Any]]] = {}
    warnings_by_stage: dict[str, list[dict[str, Any]]] = {}
    for domain in domains.values():
        if not isinstance(domain, dict):
            continue
        for item in domain.get("blockers", []) if isinstance(domain.get("blockers"), list) else []:
            if isinstance(item, dict):
                blockers_by_stage.setdefault(str(item.get("stage") or "release_ready"), []).append(item)
        for item in domain.get("warnings", []) if isinstance(domain.get("warnings"), list) else []:
            if isinstance(item, dict):
                warnings_by_stage.setdefault(str(item.get("stage") or "release_ready"), []).append(item)
    statuses: list[dict[str, Any]] = []
    for stage in OPERATIONS_STAGES:
        if stage == "draft":
            statuses.append({"stage": stage, "status": "passed"})
            continue
        if stage == "archived":
            statuses.append({"stage": stage, "status": "pending"})
            continue
        failed = blockers_by_stage.get(stage, [])
        warning_count = len(warnings_by_stage.get(stage, []))
        status = "failed" if failed else "warning" if warning_count else "passed"
        statuses.append({"stage": stage, "status": status, "blocker_count": len(failed), "warning_count": warning_count})
    return statuses


def _current_stage(stage_statuses: list[ImplementationDocument]) -> tuple[str, str | None]:
    current = "draft"
    for item in stage_statuses:
        stage = str(item.get("stage") or "")
        if item.get("status") in {"passed", "warning"}:
            current = stage
            continue
        if stage == "archived" and item.get("status") == "pending":
            return current, stage
        return current, stage
    return current, None


def _stage_progress(stage_statuses: list[ImplementationDocument]) -> ImplementationDocument:
    total = len(stage_statuses)
    completed = sum(1 for item in stage_statuses if item.get("status") in {"passed", "warning"})
    return {"completed": completed, "total": total, "percent": int(round((completed / total) * 100)) if total else 0}


def _domain_items(domains: ImplementationDocument, key: str) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    for domain_id, domain in domains.items():
        if not isinstance(domain, dict):
            continue
        for item in domain.get(key, []) if isinstance(domain.get(key), list) else []:
            if isinstance(item, dict):
                rows.append({**item, "domain": item.get("domain") or domain_id})
    return rows


def _renumber(rows: list[ImplementationDocument], key: str, prefix: str) -> list[ImplementationDocument]:
    return [{**row, key: f"{prefix}-{index:06d}"} for index, row in enumerate(rows, start=1)]


def _package_summary(path: Path, *, status: str) -> ImplementationDocument:
    if not path or not path.exists() or not path.is_file() or path.is_symlink():
        return {"status": status, "exists": False}
    return {"status": status, "exists": True, "filename": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _package_summary_count(package_summaries: ImplementationDocument) -> int:
    count = 1 if isinstance(package_summaries.get("release_zip"), dict) and package_summaries["release_zip"].get("exists") else 0
    for key in ("distribution_packages", "submission_packages", "submission_evidence_packages"):
        count += sum(1 for item in package_summaries.get(key, []) if isinstance(item, dict) and item.get("exists"))
    return count


def _summary_status(value: ImplementationDocument | None) -> ImplementationDocument:
    data = value if isinstance(value, dict) else {}
    if not data:
        return {"status": "missing"}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata({**summary, "status": data.get("status") or summary.get("status") or "present", "source_hash": data.get("source_hash") or summary.get("source_hash"), "integrity_hash": data.get("integrity_hash") or summary.get("integrity_hash")}, blocked_keys=OPERATIONS_BLOCKED_KEYS)


def _rights_summary(report: ImplementationDocument) -> ImplementationDocument:
    if not report:
        return {"status": "missing"}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status") or summary.get("status") or "present",
            "release_id": report.get("release_id"),
            "track_count": summary.get("track_count", 0),
            "manual_cleared_track_count": summary.get("manual_cleared_track_count", 0),
            "source_usage_count": summary.get("source_usage_count", 0),
            "integrity_ok": rights_report_integrity_ok(report),
            "summary_hash": rights_summary_hash(summary) if summary else None,
        },
        blocked_keys=OPERATIONS_BLOCKED_KEYS,
    )


def _operations_signoff_summary_for_report(store: ReleaseOperationsStore, release_id: str, current_source_hash: str) -> ImplementationDocument:
    path = store.operations_dir(release_id) / "operations-signoff.json"
    if not path.exists():
        return {"status": "not_signed", "integrity_ok": False, "stale": False}
    try:
        signoff = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "failed", "integrity_ok": False, "stale": True}
    if not isinstance(signoff, dict):
        return {"status": "failed", "integrity_ok": False, "stale": True}
    payload_hash = str(signoff.get("payload_hash") or "")
    actual_hash = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "export_manifest_hash", "updated_at"}})
    integrity_ok = bool(payload_hash) and payload_hash == actual_hash
    stale = bool(signoff.get("source_hash")) and str(signoff.get("source_hash")) != str(current_source_hash)
    return sanitize_metadata(
        {
            "status": signoff.get("status") or "missing",
            "signed_at": signoff.get("signed_at"),
            "signed_by": signoff.get("signed_by"),
            "force": bool(signoff.get("force")),
            "payload_hash": signoff.get("payload_hash"),
            "integrity_ok": integrity_ok,
            "payload_hash_ok": integrity_ok,
            "stale": stale,
            "source_hash": signoff.get("source_hash"),
            "current_source_hash": current_source_hash,
        },
        blocked_keys=OPERATIONS_BLOCKED_KEYS,
    )


def _apply_operations_signoff_stage(stage_statuses: list[ImplementationDocument], signoff_summary: ImplementationDocument) -> list[ImplementationDocument]:
    rows = [dict(item) for item in stage_statuses]
    for item in rows:
        if item.get("stage") != "archived":
            continue
        status = str(signoff_summary.get("status") or "")
        if status in {"signed", "force_signed"} and signoff_summary.get("integrity_ok") and not signoff_summary.get("stale"):
            item.update({"status": "passed", "blocker_count": 0, "warning_count": 0})
        elif status in {"signed", "force_signed"}:
            item.update({"status": "failed", "blocker_count": 1, "warning_count": 0})
        else:
            item.update({"status": "pending", "blocker_count": 0, "warning_count": 0})
        break
    return rows


def _redaction_summary(value: Any) -> ImplementationDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}


def _write_readme(export_dir: Path, report: ImplementationDocument) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "MusicForge Release Operations Package",
        "",
        f"Release ID: {report.get('release_id')}",
        f"Status: {report.get('status')}",
        f"Current Stage: {report.get('current_stage')}",
        f"Next Stage: {report.get('next_stage') or '-'}",
        f"Blockers: {summary.get('blocker_count', 0)}",
        f"Warnings: {summary.get('warning_count', 0)}",
        "",
        "This package contains summary evidence only. It does not include audio, artwork, distribution packages, submission packages, or attachments.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _next_report_id(root: Path, *, existing: str | None = None) -> str:
    if existing:
        return existing
    root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 1_000_000):
        report_id = f"ops-{index:06d}"
        if not (root / f"{report_id}.json").exists():
            return report_id
    raise ReleaseOperationsError("Unable to allocate operations report id.")


def _write_json(path: Path, data: ImplementationDocument) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=OPERATIONS_BLOCKED_KEYS))


def _file_record(export_dir: Path, path: Path) -> ImplementationDocument:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(export_dir.resolve(), resolved)
        entry = _validate_relative_path(resolved.relative_to(export_dir.resolve()).as_posix())
        if entry in seen:
            raise ReleaseOperationsError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleaseOperationsError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleaseOperationsError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleaseOperationsError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseOperationsError("Refusing to operate outside release operations boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
