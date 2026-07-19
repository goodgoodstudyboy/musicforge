# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, as_text as _as_text
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
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

ReleaseOperationsStore = _make_deferred_global('ReleaseOperationsStore')
_action_for_check = _make_deferred_global('_action_for_check')
_package_summary = _make_deferred_global('_package_summary')
_rights_summary = _make_deferred_global('_rights_summary')
_summary_status = _make_deferred_global('_summary_status')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleaseOperationsStore, _action_for_check, _package_summary, _rights_summary, _summary_status
    ReleaseOperationsStore = namespace.get('ReleaseOperationsStore', ReleaseOperationsStore)
    _action_for_check = namespace.get('_action_for_check', _action_for_check)
    _package_summary = namespace.get('_package_summary', _package_summary)
    _rights_summary = namespace.get('_rights_summary', _rights_summary)
    _summary_status = namespace.get('_summary_status', _summary_status)
    _bind_deferred_defaults(namespace)


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




class _OperationsCollector:
    def __init__(self, store: ReleaseOperationsStore, release_id: str, now: str) -> None:
        self.store = store
        self.release_id = release_id
        self.now = now
        self.release = store.release_store.get_release(release_id)
        self.nodes: list[DomainDocument] = []
        self.edges: list[DomainDocument] = []

    def collect(self) -> tuple[DomainDocument, DomainDocument, DomainDocument, DomainDocument, DomainDocument]:
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

    def _release_domain(self) -> tuple[DomainDocument, DomainDocument, DomainDocument, DomainDocument]:
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
        verifier_summary: DomainDocument = {"status": "missing"}
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

    def _metadata_domain(self) -> tuple[DomainDocument, DomainDocument]:
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

    def _audio_domain(self) -> tuple[DomainDocument, DomainDocument]:
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

    def _rights_domain(self) -> tuple[DomainDocument, DomainDocument]:
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

    def _format_domain(self) -> tuple[DomainDocument, DomainDocument]:
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

    def _distribution_domain(self) -> tuple[DomainDocument, list[DomainDocument], list[DomainDocument], list[DomainDocument]]:
        targets = self.store.distribution_store.list_targets(self.release_id)
        rows: list[DomainDocument] = []
        verifiers: list[DomainDocument] = []
        packages: list[DomainDocument] = []
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
            verifier_summary: DomainDocument = {"status": "missing", "target_id": target.target_id, "package_id": package_id}
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

    def _submission_domain(self) -> tuple[DomainDocument, list[DomainDocument], list[DomainDocument], list[DomainDocument]]:
        batches = self.store.submission_store.list_submissions(self.release_id)
        rows: list[DomainDocument] = []
        verifiers: list[DomainDocument] = []
        packages: list[DomainDocument] = []
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
            verifier_summary: DomainDocument = {"status": "missing", "submission_id": batch.submission_id}
            if zip_path.exists():
                try:
                    verifier_summary = submission_verification_summary(verify_submission_package(zip_path))
                except Exception as exc:
                    verifier_summary = {"status": "failed", "submission_id": batch.submission_id, "error": str(exc)}
            verifiers.append(verifier_summary)
            packages.append({**package_summary, "submission_id": batch.submission_id, "verify_status": verifier_summary.get("status")})
            row: DomainDocument = {"submission": batch_summary, "qa_summary": _summary_status(qa), "export_summary": export_summary, "signoff_summary": submission_signoff_summary(signoff), "package_summary": package_summary, "verifier_summary": verifier_summary, "items": [item.to_dict() for item in batch.items]}
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

    def _submission_evidence_domain(self) -> tuple[DomainDocument, list[DomainDocument], list[DomainDocument], list[DomainDocument]]:
        batches = self.store.submission_store.list_submissions(self.release_id)
        rows: list[DomainDocument] = []
        verifiers: list[DomainDocument] = []
        packages: list[DomainDocument] = []
        domain = _domain("submission_evidence", "passed" if not batches else "pending", summary={"submission_count": len(batches)}, required=bool(batches))
        for batch in batches:
            report = self.store.submission_evidence_store.read_report(self.release_id, batch.submission_id, default={})
            signoff = self.store.submission_evidence_store.read_signoff(self.release_id, batch.submission_id, default={})
            try:
                manifest = self.store.submission_evidence_store.read_export_manifest(self.release_id, batch.submission_id)
            except Exception:
                manifest = {}
            zip_path = self.store.submission_evidence_store.package_zip_path(self.release_id, batch.submission_id)
            verifier_summary: DomainDocument = {"status": "missing", "submission_id": batch.submission_id}
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
            self._node(f"submission_evidence:{batch.submission_id}", "submission_evidence", f"Evidence {batch.submission_id}", _as_text(signoff_summary.get("status") or report_summary.get("status")))
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

    def _exports_domain(self, release_source: DomainDocument, distribution_source: list[DomainDocument], submission_source: list[DomainDocument], evidence_source: list[DomainDocument]) -> DomainDocument:
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

    def _verifiers_domain(self, summaries: list[DomainDocument]) -> DomainDocument:
        failed = [item for item in summaries if item.get("status") not in {"passed", "warning", "missing"}]
        domain = _domain("verifiers", "passed", summary={"verifier_count": len(summaries), "failed_count": len(failed)}, required=False)
        for item in failed:
            _add_blocker_action(domain, str(item.get("release_id") or item.get("target_id") or item.get("submission_id") or "package"), "package_verifier_failed", "A package verifier failed.", _action_for_check("package_verifier_failed"), stage="release_ready")
        _finalize_domain(domain, optional_missing_pass=True)
        return domain

    def _optional_domain(self, domain_id: str, status: str, summary: DomainDocument, *, required: bool) -> DomainDocument:
        domain = _domain(domain_id, status, summary=summary, required=required)
        _finalize_domain(domain, optional_missing_pass=True)
        return domain

    def _node(self, node_id: str, node_type: str, label: str, status: str) -> None:
        self.nodes.append({"id": node_id, "type": node_type, "label": sanitize_sensitive_text(label), "status": status or "missing"})

    def _edge(self, source: str, target: str, relation: str) -> None:
        self.edges.append({"from": source, "to": target, "relation": relation})

def operations_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == operations_report_integrity_hash(data)

def operations_report_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
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

def _domain(domain_id: str, status: str, *, summary: DomainDocument, required: bool) -> DomainDocument:
    return {"status": status, "summary": summary, "required": required, "stale": False, "blocker_count": 0, "warning_count": 0, "blockers": [], "warnings": [], "next_actions": [], "source_hash": stable_hash(summary)}

def _finalize_domain(domain: DomainDocument, *, optional_missing_pass: bool = False) -> None:
    blockers = _as_list(domain.get("blockers"))
    warnings = _as_list(domain.get("warnings"))
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

def _add_blocker_action(domain: DomainDocument, entity_id: str, check_id: str, message: str, action: DomainDocument, *, stage: str) -> None:
    blocker = _blocker(domain=action.get("domain") or "release", scope=action.get("scope") or action.get("domain") or "release", entity_id=entity_id, check_id=check_id, message=message, recommended_action=action.get("description") or action.get("label") or "", action_hint=action.get("action_type") or "", stage=stage)
    domain.setdefault("blockers", []).append(blocker)
    domain.setdefault("next_actions", []).append({**action, "entity_id": entity_id, "unblocks": [stage], "blocked_by": [check_id]})

def _add_warning_action(domain: DomainDocument, entity_id: str, check_id: str, message: str, action: DomainDocument, *, stage: str) -> None:
    warning = {"domain": action.get("domain") or "release", "scope": action.get("scope") or action.get("domain") or "release", "entity_id": entity_id, "check_id": check_id, "severity": "warning", "message": message, "recommended_action": action.get("description") or action.get("label") or "", "action_hint": action.get("action_type") or "", "stage": stage}
    domain.setdefault("warnings", []).append(sanitize_metadata(warning, blocked_keys=OPERATIONS_BLOCKED_KEYS))
    domain.setdefault("next_actions", []).append({**action, "entity_id": entity_id, "unblocks": [stage], "blocked_by": [check_id]})

def _blocker(*, domain: str, scope: str, entity_id: str, check_id: str, message: str, recommended_action: str, action_hint: str, stage: str) -> DomainDocument:
    return sanitize_metadata({"domain": domain, "scope": scope, "entity_id": entity_id, "check_id": check_id, "severity": "blocking", "message": message, "recommended_action": recommended_action, "action_hint": action_hint, "stage": stage}, blocked_keys=OPERATIONS_BLOCKED_KEYS)
