# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
import html as html
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model import accepted_evidence_verification_summary_from_portfolio_dir as accepted_evidence_verification_summary_from_portfolio_dir
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal as verify_release_portfolio_governance_attestation_portal
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry as verify_release_portfolio_governance_attestation_registry
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore as ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore, verification_hash as ack_verification_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import verify_release_portfolio_governance_attestation_transparency_acknowledgement_package as verify_release_portfolio_governance_attestation_transparency_acknowledgement_package
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_verifier import verify_release_portfolio_governance_attestation_transparency as verify_release_portfolio_governance_attestation_transparency
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_contracts import PTC_BLOCKED_KEYS as PTC_BLOCKED_KEYS, PTC_HTML_PAGES as PTC_HTML_PAGES, PTC_MANIFEST_HASH_EXCLUDE_KEYS as PTC_MANIFEST_HASH_EXCLUDE_KEYS, PTC_PACKAGE_TYPE as PTC_PACKAGE_TYPE, PTC_REPORT_HASH_EXCLUDE_KEYS as PTC_REPORT_HASH_EXCLUDE_KEYS, _DELIVERY_COLLECTION_DOMAINS as _DELIVERY_COLLECTION_DOMAINS, _delivery_item_status as _delivery_item_status, _delivery_public_payload as _delivery_public_payload, _delivery_summary_from_item as _delivery_summary_from_item, _delivery_summary_key as _delivery_summary_key, _delivery_verification_index_from_sidecars as _delivery_verification_index_from_sidecars, _delivery_verification_index_from_source as _delivery_verification_index_from_source, _fingerprint_key as _fingerprint_key, _html_shell as _html_shell, _kv as _kv, _links as _links, _package_index as _package_index, _package_verification_index_from_sidecars as _package_verification_index_from_sidecars, _package_verification_sidecars as _package_verification_sidecars, _table as _table, _verification_index as _verification_index, _verification_sidecars as _verification_sidecars, _verification_sidecars_from_docs as _verification_sidecars_from_docs, expected_public_trust_center_documents as expected_public_trust_center_documents, public_trust_center_data_documents as public_trust_center_data_documents, public_trust_center_html_pages as public_trust_center_html_pages, public_trust_center_manifest_hash as public_trust_center_manifest_hash, public_trust_center_report_hash as public_trust_center_report_hash

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

PublicTrustCenterStateError = _make_deferred_global('PublicTrustCenterStateError')
_aggregate_status = _make_deferred_global('_aggregate_status')
_delivery_fingerprint_sidecar_document = _make_deferred_global('_delivery_fingerprint_sidecar_document')
_delivery_fingerprint_sidecar_path = _make_deferred_global('_delivery_fingerprint_sidecar_path')
_delivery_readiness_matrix_from_parts = _make_deferred_global('_delivery_readiness_matrix_from_parts')
_delivery_sidecar_document = _make_deferred_global('_delivery_sidecar_document')
_delivery_sidecar_path = _make_deferred_global('_delivery_sidecar_path')
_domain_not_configured_row = _make_deferred_global('_domain_not_configured_row')
_latest_feedback_status = _make_deferred_global('_latest_feedback_status')
_nested_status = _make_deferred_global('_nested_status')
_package_report_current_status = _make_deferred_global('_package_report_current_status')
_package_status_from_fingerprints = _make_deferred_global('_package_status_from_fingerprints')
_read_json_default = _make_deferred_global('_read_json_default')
_sanitize_public_metadata = _make_deferred_global('_sanitize_public_metadata')
_sha256 = _make_deferred_global('_sha256')
_stable_hash_without_zip = _make_deferred_global('_stable_hash_without_zip')
_verification_current_status = _make_deferred_global('_verification_current_status')
_verification_hash = _make_deferred_global('_verification_hash')
_verification_sidecar_document = _make_deferred_global('_verification_sidecar_document')
_verification_sidecar_path = _make_deferred_global('_verification_sidecar_path')
public_trust_center_report_integrity_ok = _make_deferred_global('public_trust_center_report_integrity_ok')

def bind_globals(namespace: dict[str, object]) -> None:
    global PublicTrustCenterStateError, _aggregate_status, _delivery_fingerprint_sidecar_document, _delivery_fingerprint_sidecar_path, _delivery_readiness_matrix_from_parts, _delivery_sidecar_document, _delivery_sidecar_path, _domain_not_configured_row
    global _latest_feedback_status, _nested_status, _package_report_current_status, _package_status_from_fingerprints, _read_json_default, _sanitize_public_metadata, _sha256
    global _stable_hash_without_zip, _verification_current_status, _verification_hash, _verification_sidecar_document, _verification_sidecar_path, public_trust_center_report_integrity_ok
    PublicTrustCenterStateError = namespace.get('PublicTrustCenterStateError', PublicTrustCenterStateError)
    _aggregate_status = namespace.get('_aggregate_status', _aggregate_status)
    _delivery_fingerprint_sidecar_document = namespace.get('_delivery_fingerprint_sidecar_document', _delivery_fingerprint_sidecar_document)
    _delivery_fingerprint_sidecar_path = namespace.get('_delivery_fingerprint_sidecar_path', _delivery_fingerprint_sidecar_path)
    _delivery_readiness_matrix_from_parts = namespace.get('_delivery_readiness_matrix_from_parts', _delivery_readiness_matrix_from_parts)
    _delivery_sidecar_document = namespace.get('_delivery_sidecar_document', _delivery_sidecar_document)
    _delivery_sidecar_path = namespace.get('_delivery_sidecar_path', _delivery_sidecar_path)
    _domain_not_configured_row = namespace.get('_domain_not_configured_row', _domain_not_configured_row)
    _latest_feedback_status = namespace.get('_latest_feedback_status', _latest_feedback_status)
    _nested_status = namespace.get('_nested_status', _nested_status)
    _package_report_current_status = namespace.get('_package_report_current_status', _package_report_current_status)
    _package_status_from_fingerprints = namespace.get('_package_status_from_fingerprints', _package_status_from_fingerprints)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _sanitize_public_metadata = namespace.get('_sanitize_public_metadata', _sanitize_public_metadata)
    _sha256 = namespace.get('_sha256', _sha256)
    _stable_hash_without_zip = namespace.get('_stable_hash_without_zip', _stable_hash_without_zip)
    _verification_current_status = namespace.get('_verification_current_status', _verification_current_status)
    _verification_hash = namespace.get('_verification_hash', _verification_hash)
    _verification_sidecar_document = namespace.get('_verification_sidecar_document', _verification_sidecar_document)
    _verification_sidecar_path = namespace.get('_verification_sidecar_path', _verification_sidecar_path)
    public_trust_center_report_integrity_ok = namespace.get('public_trust_center_report_integrity_ok', public_trust_center_report_integrity_ok)
    _bind_deferred_defaults(namespace)


PTC_SCHEMA_VERSION = 1
PTC_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_report"
PTC_CONFIG_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
PTC_DELIVERY_DOMAINS = ("release", "distribution", "submission", "submission_evidence", "operations", "operations_audit", "operations_reviewer_pack")




class PublicTrustCenterStoreEvidenceMixin:
    def _distribution_summaries(self, release_ids: list[str]) -> list[DomainDocument]:
        if self.distribution_store is None:
            return [_domain_not_configured_row("distribution", release_id) for release_id in release_ids]
        rows: list[DomainDocument] = []
        for release_id in release_ids:
            try:
                targets = self.distribution_store.list_targets(release_id)
            except Exception as exc:
                rows.append({"release_id": release_id, "target_id": None, "status": "failed", "verification_status": "failed", "error": str(exc)})
                continue
            if not targets:
                rows.append({"release_id": release_id, "target_id": None, "status": "missing", "verification_status": "missing", "package_zip_status": "missing"})
                continue
            for target in targets:
                package_id = None
                try:
                    package_id = self.distribution_store.latest_package_id(target)
                except Exception:
                    package_id = None
                signoff = {}
                try:
                    signoff = self.distribution_store.read_signoff(release_id, target, default={})
                except Exception:
                    signoff = {}
                manifest_path = self.distribution_store.export_dir(release_id, package_id) / "distribution-manifest.json" if package_id else None
                manifest = _read_json_default(manifest_path, default={}) if manifest_path else {}
                zip_path = self.distribution_store.package_zip_path(release_id, package_id) if package_id else None
                verification_path = self.distribution_store.package_dir(release_id, package_id) / "verification-report.json" if package_id else None
                verification = _read_json_default(verification_path, default={}) if verification_path else {}
                qa = {}
                try:
                    qa = self.distribution_store.read_qa(release_id, target.target_id, default={})
                except Exception:
                    qa = {}
                row = {
                    "release_id": release_id,
                    "target_id": target.target_id,
                    "package_id": package_id,
                    "platform": getattr(target, "profile_id", None),
                    "profile_id": getattr(target, "profile_id", None),
                    "name": getattr(target, "name", None),
                    "status": getattr(target, "status", "missing"),
                    "signoff_status": signoff.get("status") or target.latest_signoff_summary.get("status") or "missing",
                    "package_zip_status": "exists" if zip_path and zip_path.exists() else "missing",
                    "package_zip_sha256": _sha256(zip_path) if zip_path else None,
                    "package_zip_size_bytes": zip_path.stat().st_size if zip_path and zip_path.exists() else None,
                    "manifest_hash": manifest.get("integrity_hash") or _stable_hash_without_zip(manifest),
                    "verification_status": _package_report_current_status(verification, zip_path, manifest),
                    "verification_hash": _verification_hash(verification),
                    "verification_report_status": verification.get("status") or "missing",
                    "checklist_status": _nested_status(manifest, ("checklist", "status"), default=qa.get("status") or "missing"),
                    "rights_status": _nested_status(manifest, ("rights_clearance", "status"), default="missing"),
                    "format_decision_status": _nested_status(manifest, ("format_decision", "status"), default="missing"),
                    "encoded_audio_status": _nested_status(manifest, ("encoded_audio", "status"), default="missing"),
                    "template_pack_id": getattr(target, "template_pack_id", None),
                    "updated_at": getattr(target, "updated_at", None),
                }
                row["fingerprint_hash"] = stable_hash(row)
                rows.append(_sanitize_public_metadata(row))
        return sorted(rows, key=lambda item: (str(item.get("release_id")), str(item.get("target_id"))))

    def _submission_summaries(self, release_ids: list[str]) -> list[DomainDocument]:
        if self.submission_store is None:
            return [_domain_not_configured_row("submission", release_id) for release_id in release_ids]
        rows: list[DomainDocument] = []
        for release_id in release_ids:
            try:
                submissions = self.submission_store.list_submissions(release_id)
            except Exception as exc:
                rows.append({"release_id": release_id, "submission_id": None, "status": "failed", "verification_status": "failed", "error": str(exc)})
                continue
            if not submissions:
                rows.append({"release_id": release_id, "submission_id": None, "status": "missing", "verification_status": "missing", "package_zip_status": "missing"})
                continue
            for batch in submissions:
                manifest_path = self.submission_store.export_dir(release_id, batch.submission_id) / "submission-manifest.json"
                manifest = _read_json_default(manifest_path, default={})
                zip_path = self.submission_store.package_zip_path(release_id, batch.submission_id)
                verification_path = self.submission_store.submission_dir(release_id, batch.submission_id) / "submission-verification-report.json"
                verification = _read_json_default(verification_path, default={})
                signoff = self.submission_store.read_signoff(release_id, batch.submission_id, default={})
                items = batch.items
                row = {
                    "release_id": release_id,
                    "submission_id": batch.submission_id,
                    "status": batch.status,
                    "signoff_status": signoff.get("status") or batch.latest_signoff_summary.get("status") or "missing",
                    "target_count": len(items),
                    "ready_count": sum(1 for item in items if item.status == "ready"),
                    "submitted_count": sum(1 for item in items if item.status in {"submitted", "feedback_received", "needs_changes", "accepted", "rejected"}),
                    "accepted_count": sum(1 for item in items if item.status == "accepted"),
                    "package_zip_status": "exists" if zip_path.exists() else "missing",
                    "package_zip_sha256": _sha256(zip_path),
                    "package_zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
                    "manifest_hash": manifest.get("integrity_hash") or _stable_hash_without_zip(manifest),
                    "verification_status": _package_report_current_status(verification, zip_path, manifest),
                    "verification_hash": _verification_hash(verification),
                    "verification_report_status": verification.get("status") or "missing",
                    "latest_feedback_status": _latest_feedback_status(items),
                    "updated_at": batch.updated_at,
                }
                row["fingerprint_hash"] = stable_hash(row)
                rows.append(_sanitize_public_metadata(row))
        return sorted(rows, key=lambda item: (str(item.get("release_id")), str(item.get("submission_id"))))

    def _submission_evidence_summaries(self, submissions: list[DomainDocument]) -> list[DomainDocument]:
        if self.submission_evidence_store is None:
            return [_domain_not_configured_row("submission_evidence", str(item.get("release_id") or ""), submission_id=item.get("submission_id")) for item in submissions if item.get("submission_id")]
        rows: list[DomainDocument] = []
        for item in submissions:
            release_id = str(item.get("release_id") or "")
            submission_id = str(item.get("submission_id") or "")
            if not release_id or not submission_id:
                continue
            report = self.submission_evidence_store.read_report(release_id, submission_id, default={})
            signoff = self.submission_evidence_store.read_signoff(release_id, submission_id, default={})
            manifest_path = self.submission_evidence_store.export_dir(release_id, submission_id) / "submission-evidence-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            zip_path = self.submission_evidence_store.package_zip_path(release_id, submission_id)
            verification_path = self.submission_store.submission_dir(release_id, submission_id) / "submission-evidence-verification-report.json" if self.submission_store else None
            verification = _read_json_default(verification_path, default={}) if verification_path else {}
            summary = _as_document(report.get("summary"))
            row = {
                "release_id": release_id,
                "submission_id": submission_id,
                "report_status": report.get("status") or "missing",
                "report_hash": report.get("integrity_hash"),
                "signoff_status": signoff.get("status") or "missing",
                "signoff_hash": signoff.get("payload_hash"),
                "package_zip_status": "exists" if zip_path.exists() else "missing",
                "package_zip_sha256": _sha256(zip_path),
                "package_zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
                "manifest_hash": manifest.get("integrity_hash") or _stable_hash_without_zip(manifest),
                "verification_status": _package_report_current_status(verification, zip_path, manifest),
                "verification_hash": _verification_hash(verification),
                "verification_report_status": verification.get("status") or "missing",
                "accepted_evidence_count": summary.get("accepted_count", 0),
                "attachment_count": summary.get("attachment_count", 0),
                "redaction_status": (_as_document(manifest.get("redaction_summary"))).get("status") or "missing",
            }
            row["fingerprint_hash"] = stable_hash(row)
            rows.append(_sanitize_public_metadata(row))
        return sorted(rows, key=lambda row: (str(row.get("release_id")), str(row.get("submission_id"))))

    def _operations_summaries(self, release_ids: list[str]) -> list[DomainDocument]:
        if self.operations_store is None:
            return [_domain_not_configured_row("operations", release_id) for release_id in release_ids]
        rows: list[DomainDocument] = []
        for release_id in release_ids:
            report = self.operations_store.read_report(release_id, default={})
            report_summary = _as_document(report.get("summary"))
            report_status = report.get("status") or "missing"
            signoff = self.operations_signoff_store.read_signoff(release_id, default={}) if self.operations_signoff_store is not None else {}
            report_signoff = _as_document(report_summary.get("operations_signoff"))
            signoff_status = signoff.get("status") or report_signoff.get("status")
            runbook_summary = self._latest_runbook_summary(release_id)
            packages = self._operations_package_fingerprints(release_id)
            audit_summary = self.operations_audit_store.summary(release_id) if self.operations_audit_store is not None else {"status": "not_configured"}
            reviewer_summary = self.operations_reviewer_pack_store.summary(release_id) if self.operations_reviewer_pack_store is not None else {"status": "not_configured"}
            row = {
                "release_id": release_id,
                "operations_report_status": report_status,
                "operations_report_hash": report.get("integrity_hash"),
                "operations_source_hash": report.get("source_hash"),
                "operations_signoff_status": signoff_status or "missing",
                "operations_signoff_hash": signoff.get("payload_hash"),
                "operations_archive_status": _package_status_from_fingerprints(packages, "operations_archive"),
                "operations_audit_status": audit_summary.get("status") or _package_status_from_fingerprints(packages, "operations_audit"),
                "operations_reviewer_pack_status": reviewer_summary.get("status") or _package_status_from_fingerprints(packages, "operations_reviewer_pack"),
                "runbook_status": runbook_summary.get("status") or "missing",
                "change_request_count": len(self.operations_signoff_store.list_change_requests(release_id)) if self.operations_signoff_store is not None else 0,
                "package_fingerprints": packages,
            }
            row["fingerprint_hash"] = stable_hash(row)
            rows.append(_sanitize_public_metadata(row))
        return sorted(rows, key=lambda row: str(row.get("release_id") or ""))

    def _latest_runbook_summary(self, release_id: str) -> DomainDocument:
        if self.operations_runbook_store is None:
            return {"status": "not_configured"}
        try:
            rows = self.operations_runbook_store.list_runbooks(release_id, include_archived=True)
        except Exception:
            return {"status": "missing"}
        if not rows:
            return {"status": "missing"}
        latest = rows[0]
        return {
            "runbook_id": latest.get("runbook_id"),
            "status": latest.get("status") or "missing",
            "source_hash": (_as_document(latest.get("source"))).get("operations_source_hash"),
            "integrity_hash": latest.get("integrity_hash"),
        }

    def _operations_package_fingerprints(self, release_id: str) -> list[DomainDocument]:
        rows: list[DomainDocument] = []
        if self.operations_store is not None:
            rows.append(self._generic_package_fingerprint(
                "operations",
                release_id,
                self.operations_store.zip_path(release_id),
                self.operations_store.export_dir(release_id) / "operations-manifest.json",
                self.operations_store.operations_dir(release_id) / "operations-verification-report.json",
            ))
        if self.operations_signoff_store is not None:
            rows.append(self._generic_package_fingerprint(
                "operations_archive",
                release_id,
                self.operations_signoff_store.archive_zip_path(release_id),
                self.operations_signoff_store.archive_export_dir(release_id) / "operations-archive-manifest.json",
                self.operations_signoff_store.operations_dir(release_id) / "operations-archive-verification-report.json",
            ))
        if self.operations_audit_store is not None:
            rows.append(self._generic_package_fingerprint(
                "operations_audit",
                release_id,
                self.operations_audit_store.zip_path(release_id),
                self.operations_audit_store.export_dir(release_id) / "operations-audit-manifest.json",
                self.operations_audit_store.verification_report_path(release_id),
            ))
        if self.operations_reviewer_pack_store is not None:
            rows.append(self._generic_package_fingerprint(
                "operations_reviewer_pack",
                release_id,
                self.operations_reviewer_pack_store.zip_path(release_id),
                self.operations_reviewer_pack_store.export_dir(release_id) / "reviewer-pack-manifest.json",
                self.operations_reviewer_pack_store.verification_report_path(release_id),
            ))
        return [row for row in rows if row]

    def _generic_package_fingerprint(self, package_type: str, release_id: str, zip_path: Path, manifest_path: Path, verification_report_path: Path) -> DomainDocument:
        manifest = _read_json_default(manifest_path, default={})
        verification = _read_json_default(verification_report_path, default={})
        row = {
            "release_id": release_id,
            "package_type": package_type,
            "zip_sha256": _sha256(zip_path),
            "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
            "manifest_hash": manifest.get("integrity_hash") or _stable_hash_without_zip(manifest),
            "verification_status": _package_report_current_status(verification, zip_path, manifest),
            "verification_hash": _verification_hash(verification),
            "verification_report_status": verification.get("status") or "missing",
        }
        row["fingerprint_hash"] = stable_hash(row)
        return _sanitize_public_metadata(row)

    def _portfolio_summaries(self, selection: DomainDocument, *, profile: str) -> list[DomainDocument]:
        ids = [str(item).strip() for item in selection.get("portfolio_ids", []) if str(item).strip()] if isinstance(selection.get("portfolio_ids"), list) else []
        if not ids and bool(selection.get("include_all_portfolios", True)):
            try:
                ids = [str(item.get("portfolio_id")) for item in self.portfolio_store.list_portfolios(include_archived=False) if item.get("portfolio_id")]
            except Exception:
                ids = []
        rows: list[DomainDocument] = []
        for portfolio_id in sorted(dict.fromkeys(ids)):
            rows.append(self._portfolio_summary(portfolio_id, profile=profile))
        return rows

    def _portfolio_summary(self, portfolio_id: str, *, profile: str) -> DomainDocument:
        portfolio = {}
        try:
            portfolio = self.portfolio_store.get_portfolio(portfolio_id)
        except Exception:
            portfolio = {"portfolio_id": portfolio_id, "status": "missing"}
        registry = self._package_summary("registry", portfolio_id, profile, self.registry_store.zip_path(portfolio_id, profile), self.registry_store.export_dir(portfolio_id, profile) / "manifest.json", self.registry_store.verification_report_path(portfolio_id, profile))
        portal = self._package_summary("portal", portfolio_id, profile, self.portal_store.zip_path(portfolio_id, profile), self.portal_store.export_dir(portfolio_id, profile) / "portal-manifest.json", self.portal_store.verification_report_path(portfolio_id, profile))
        transparency = self._package_summary("transparency", portfolio_id, profile, self.transparency_store.zip_path(portfolio_id, profile), self.transparency_store.export_dir(portfolio_id, profile) / "transparency-manifest.json", self.transparency_store.verification_report_path(portfolio_id, profile))
        ack = self._package_summary("transparency_acknowledgement", portfolio_id, profile, self.acknowledgement_store.evidence_zip_path(portfolio_id, profile), self.acknowledgement_store.evidence_export_dir(portfolio_id, profile) / "acknowledgement-evidence-manifest.json", self.acknowledgement_store.evidence_verification_report_path(portfolio_id, profile))
        public_packages = [registry["package"], portal["package"], transparency["package"], ack["package"]]
        verification_summaries = [registry["verification"], portal["verification"], transparency["verification"], ack["verification"]]
        accepted_verification = accepted_evidence_verification_summary_from_portfolio_dir(self._portfolio_dir(portfolio_id), profile=profile)
        return sanitize_metadata(
            {
                "portfolio_id": portfolio_id,
                "name": portfolio.get("name") or portfolio.get("title") or portfolio_id,
                "status": portfolio.get("status") or "active",
                "profile": profile,
                "public_package_status": _aggregate_status([item.get("verification_status") for item in public_packages]),
                "public_packages": public_packages,
                "verification_summaries": verification_summaries,
                "registry_summary": registry["summary"],
                "portal_summary": portal["summary"],
                "transparency_summary": transparency["summary"],
                "acknowledgement_summary": ack["summary"],
                "accepted_evidence_verification": accepted_verification,
            },
            blocked_keys=PTC_BLOCKED_KEYS,
        )

    def _package_summary(self, package_type: str, portfolio_id: str, profile: str, zip_path: Path, manifest_path: Path, verification_report_path: Path) -> DomainDocument:
        manifest = _read_json_default(manifest_path, default={})
        summary: DomainDocument = {}
        verification = _read_json_default(verification_report_path, default={})
        current_zip_sha256 = _sha256(zip_path)
        current_zip_size = zip_path.stat().st_size if zip_path.exists() and zip_path.is_file() else None
        current_manifest_hash = manifest.get("integrity_hash") if isinstance(manifest, dict) else None
        verification_hash = _verification_hash(verification)
        verification_status = _verification_current_status(verification, current_zip_sha256, current_zip_size, current_manifest_hash)
        package = {
            "portfolio_id": portfolio_id,
            "profile": profile,
            "package_type": package_type,
            "zip_sha256": current_zip_sha256,
            "zip_size_bytes": current_zip_size,
            "manifest_hash": current_manifest_hash or verification.get("manifest_hash"),
            "verification_hash": verification_hash,
            "verification_status": verification_status,
            "verification_report_hash": verification_hash,
            "verification_report_status": verification.get("status") or "missing",
        }
        if isinstance(verification.get("summary"), dict):
            summary = dict(verification["summary"])
        return {"package": package, "verification": {**package, "blocker_count": len(verification.get("blockers", []) if isinstance(verification.get("blockers"), list) else [])}, "summary": summary}

    def _verification_sidecar_documents(self, source: DomainDocument) -> dict[str, DomainDocument]:
        docs: dict[str, DomainDocument] = {}
        for item in source.get("public_package_fingerprints", []) if isinstance(source.get("public_package_fingerprints"), list) else []:
            if not isinstance(item, dict):
                continue
            portfolio_id = str(item.get("portfolio_id") or "")
            profile = str(item.get("profile") or "public_summary")
            package_type = str(item.get("package_type") or "")
            report_path = self._stored_verification_report_path(package_type, portfolio_id, profile)
            verification_report = _read_json_default(report_path, default={}) if report_path else {}
            path = _verification_sidecar_path(portfolio_id, profile, package_type)
            docs[path] = _verification_sidecar_document(item, verification_report)
        return docs

    def _delivery_sidecar_documents(self, source: DomainDocument) -> dict[str, DomainDocument]:
        docs: dict[str, DomainDocument] = {}
        for collection, domain in _DELIVERY_COLLECTION_DOMAINS:
            rows = source.get(collection, []) if isinstance(source.get(collection), list) else []
            for item in rows:
                if not isinstance(item, dict):
                    continue
                release_id = str(item.get("release_id") or "")
                entity_id = str(item.get("target_id") or item.get("submission_id") or item.get("release_id") or "summary")
                if not release_id:
                    continue
                summary_path = _delivery_sidecar_path(domain, release_id, entity_id)
                fingerprint_path = _delivery_fingerprint_sidecar_path(domain, release_id, entity_id)
                independent_item = self._independent_delivery_sidecar_item(domain, item)
                fingerprint_doc = _delivery_fingerprint_sidecar_document(domain, independent_item, fingerprint_path)
                docs[summary_path] = _delivery_sidecar_document(domain, independent_item, fingerprint_path=fingerprint_path, fingerprint_hash=stable_hash(fingerprint_doc))
                docs[fingerprint_path] = fingerprint_doc
        return docs

    def _independent_delivery_sidecar_item(self, domain: str, item: DomainDocument) -> DomainDocument:
        release_id = str(item.get("release_id") or "")
        if not release_id:
            return item
        try:
            if domain == "release":
                releases = self._release_summaries({"release_ids": [release_id], "include_all_releases": False})
                distribution = self._distribution_summaries([release_id])
                submissions = self._submission_summaries([release_id])
                submission_evidence = self._submission_evidence_summaries(submissions)
                operations = self._operations_summaries([release_id])
                rows = _delivery_readiness_matrix_from_parts(releases, [], distribution, submissions, submission_evidence, operations)
                if rows:
                    row = dict(rows[0])
                    if "portfolio_public_proof_status" in item:
                        row["portfolio_public_proof_status"] = item.get("portfolio_public_proof_status")
                        row.pop("fingerprint_hash", None)
                        row["fingerprint_hash"] = stable_hash(row)
                    return row
                return dict(item)
            if domain == "distribution":
                return self._matching_delivery_row(self._distribution_summaries([release_id]), item, "target_id")
            if domain == "submission":
                return self._matching_delivery_row(self._submission_summaries([release_id]), item, "submission_id")
            if domain == "submission_evidence":
                submissions = self._submission_summaries([release_id])
                return self._matching_delivery_row(self._submission_evidence_summaries(submissions), item, "submission_id")
            if domain == "operations":
                return self._matching_delivery_row(self._operations_summaries([release_id]), item, "release_id")
        except Exception as exc:
            fallback = dict(item)
            fallback["status"] = "failed"
            fallback["verification_status"] = "failed"
            fallback["error"] = str(exc)
            return fallback
        return item

    @staticmethod
    def _matching_delivery_row(rows: list[DomainDocument], item: DomainDocument, key: str) -> DomainDocument:
        wanted = str(item.get(key) or "")
        if wanted:
            for row in rows:
                if str(row.get(key) or "") == wanted:
                    return row
        return rows[0] if rows else dict(item)

    def _stored_verification_report_path(self, package_type: str, portfolio_id: str, profile: str) -> Path | None:
        if package_type == "registry":
            return self.registry_store.verification_report_path(portfolio_id, profile)
        if package_type == "portal":
            return self.portal_store.verification_report_path(portfolio_id, profile)
        if package_type == "transparency":
            return self.transparency_store.verification_report_path(portfolio_id, profile)
        if package_type == "transparency_acknowledgement":
            return self.acknowledgement_store.evidence_verification_report_path(portfolio_id, profile)
        return None

    def _portfolio_dir(self, portfolio_id: str) -> Path:
        if hasattr(self.portfolio_store, "portfolio_dir"):
            return self.portfolio_store.portfolio_dir(portfolio_id)
        candidate = getattr(self.registry_store, "attestation_store", None)
        candidate = getattr(candidate, "portfolio_store", None)
        if candidate is not None and hasattr(candidate, "portfolio_dir"):
            return candidate.portfolio_dir(portfolio_id)
        candidate = getattr(self.transparency_store, "attestation_store", None)
        candidate = getattr(candidate, "portfolio_store", None)
        if candidate is not None and hasattr(candidate, "portfolio_dir"):
            return candidate.portfolio_dir(portfolio_id)
        raise PublicTrustCenterStateError("Public Trust Center cannot resolve portfolio evidence directory.")

    def _ensure_exportable(self, report: DomainDocument, source: DomainDocument) -> None:
        if not report:
            raise PublicTrustCenterStateError("Public Trust Center report has not been generated.")
        if str(report.get("source_hash") or "") != stable_hash(source):
            raise PublicTrustCenterStateError("Public Trust Center source is stale. Refresh before export.")
        if not public_trust_center_report_integrity_ok(report):
            raise PublicTrustCenterStateError("Public Trust Center report integrity failed.")

    def _append_history(self, center_id: str, event_type: str, payload: DomainDocument, *, now: str | None = None) -> None:
        path = self.history_path(center_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event_type": event_type, "created_at": now or now_iso(), "payload": sanitize_metadata(payload, blocked_keys=PTC_BLOCKED_KEYS)}, ensure_ascii=False, sort_keys=True) + "\n")
