# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, document_or as _document_or

import html as html
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

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
from song_agent.domains.trust.v142_ptc_readiness import PublicTrustCenterStoreReadinessMixin
from song_agent.domains.trust import v142_ptc_readiness as _v142_ptc_readiness
from song_agent.domains.trust.v142_ptc_evidence_2 import PublicTrustCenterStoreEvidenceMixin
from song_agent.domains.trust import v142_ptc_evidence_2 as _v142_ptc_evidence_2
from song_agent.domains.trust.v142_ptc_lifecycle import PublicTrustCenterStoreLifecycleMixin
from song_agent.domains.trust import v142_ptc_lifecycle as _v142_ptc_lifecycle



PTC_SCHEMA_VERSION = 1

PTC_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_report"

PTC_CONFIG_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}



PTC_DELIVERY_DOMAINS = ("release", "distribution", "submission", "submission_evidence", "operations", "operations_audit", "operations_reviewer_pack")



class PublicTrustCenterError(ValueError):
    pass


class PublicTrustCenterNotFoundError(PublicTrustCenterError):
    pass


class PublicTrustCenterStateError(PublicTrustCenterError):
    pass


class PublicTrustCenterStore(PublicTrustCenterStoreReadinessMixin, PublicTrustCenterStoreEvidenceMixin, PublicTrustCenterStoreLifecycleMixin):
    def __init__(
        self,
        *,
        release_store: ReleaseStore,
        portfolio_store: Any,
        registry_store: Any,
        portal_store: Any,
        transparency_store: Any,
        acknowledgement_store: ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore,
        distribution_store: Any | None = None,
        submission_store: Any | None = None,
        submission_evidence_store: Any | None = None,
        operations_store: Any | None = None,
        operations_runbook_store: Any | None = None,
        operations_signoff_store: Any | None = None,
        operations_audit_store: Any | None = None,
        operations_reviewer_pack_store: Any | None = None,
    ) -> None:
        self.release_store = release_store
        self.portfolio_store = portfolio_store
        self.registry_store = registry_store
        self.portal_store = portal_store
        self.transparency_store = transparency_store
        self.acknowledgement_store = acknowledgement_store
        self.distribution_store = distribution_store
        self.submission_store = submission_store
        self.submission_evidence_store = submission_evidence_store
        self.operations_store = operations_store
        self.operations_runbook_store = operations_runbook_store
        self.operations_signoff_store = operations_signoff_store
        self.operations_audit_store = operations_audit_store
        self.operations_reviewer_pack_store = operations_reviewer_pack_store
        self.root = release_store.root.parent / "public-trust-centers"
        self.lock = threading.RLock()













































def public_trust_center_config_hash(config: DomainDocument) -> str:
    return stable_hash({key: value for key, value in config.items() if key not in PTC_CONFIG_HASH_EXCLUDE_KEYS})








def public_trust_center_report_integrity_ok(report: DomainDocument) -> bool:
    return bool(report) and str(report.get("integrity_hash") or "") == public_trust_center_report_hash(report)


def public_trust_center_manifest_integrity_ok(manifest: DomainDocument) -> bool:
    return bool(manifest) and str(manifest.get("integrity_hash") or "") == public_trust_center_manifest_hash(manifest)


def public_trust_center_config_summary(config: DomainDocument) -> DomainDocument:
    return {"center_id": config.get("center_id"), "name": config.get("name"), "updated_at": config.get("updated_at"), "integrity_ok": str(config.get("integrity_hash") or "") == public_trust_center_config_hash(config)}


def public_trust_center_summary(report: DomainDocument) -> DomainDocument:
    if not report:
        return {"status": "missing"}
    summary = dict(_as_document(report.get("summary")))
    summary.update({"center_id": report.get("center_id"), "status": report.get("status"), "readiness": report.get("readiness"), "source_hash": report.get("source_hash"), "integrity_ok": public_trust_center_report_integrity_ok(report)})
    return summary


def public_trust_center_summary_from_source(source: DomainDocument, blockers: list[DomainDocument], warnings: list[DomainDocument]) -> DomainDocument:
    package_count = len(source.get("public_package_fingerprints", []) if isinstance(source.get("public_package_fingerprints"), list) else [])
    verification_count = len(source.get("verification_fingerprints", []) if isinstance(source.get("verification_fingerprints"), list) else [])
    passed_verifications = sum(1 for item in source.get("verification_fingerprints", []) if isinstance(item, dict) and item.get("verification_status") == "passed")
    delivery_rows = source.get("release_delivery_summaries", []) if isinstance(source.get("release_delivery_summaries"), list) else []
    distribution_rows = source.get("distribution_summaries", []) if isinstance(source.get("distribution_summaries"), list) else []
    submission_rows = source.get("submission_summaries", []) if isinstance(source.get("submission_summaries"), list) else []
    operations_rows = source.get("operations_summaries", []) if isinstance(source.get("operations_summaries"), list) else []
    return {
        "center_id": source.get("center_id"),
        "profile": source.get("profile"),
        "release_count": int(source.get("release_count") or 0),
        "portfolio_count": int(source.get("portfolio_count") or 0),
        "public_package_count": package_count,
        "verification_count": verification_count,
        "passed_verification_count": passed_verifications,
        "delivery_release_count": len(delivery_rows),
        "delivery_ready_count": sum(1 for item in delivery_rows if isinstance(item, dict) and item.get("readiness") == "ready"),
        "distribution_ready_count": sum(1 for item in distribution_rows if isinstance(item, dict) and item.get("readiness") == "ready"),
        "submission_accepted_count": sum(1 for item in submission_rows if isinstance(item, dict) and item.get("accepted_count", 0)),
        "operations_signed_count": sum(1 for item in operations_rows if isinstance(item, dict) and item.get("operations_signoff_status") in {"signed", "force_signed"}),
        "delivery_risk_count": len(source.get("delivery_risk_register", []) if isinstance(source.get("delivery_risk_register"), list) else []),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "readiness": "blocked" if blockers else "review_needed" if warnings else "public_trust_ready",
    }











def _normalize_selection(payload: ImplementationDocument) -> ImplementationDocument:
    return {
        "release_ids": [str(item).strip() for item in payload.get("release_ids", []) if str(item).strip()] if isinstance(payload.get("release_ids"), list) else [],
        "portfolio_ids": [str(item).strip() for item in payload.get("portfolio_ids", []) if str(item).strip()] if isinstance(payload.get("portfolio_ids"), list) else [],
        "include_all_releases": bool(payload.get("include_all_releases", True)),
        "include_all_portfolios": bool(payload.get("include_all_portfolios", True)),
        "attestation_profile": str(payload.get("attestation_profile") or payload.get("profile") or "public_summary"),
        "include_distribution": bool(payload.get("include_distribution", payload.get("include_delivery", True))),
        "include_submission": bool(payload.get("include_submission", payload.get("include_delivery", True))),
        "include_submission_evidence": bool(payload.get("include_submission_evidence", payload.get("include_submission", payload.get("include_delivery", True)))),
        "include_operations": bool(payload.get("include_operations", payload.get("include_delivery", True))),
    }


def _normalize_policy(payload: ImplementationDocument) -> ImplementationDocument:
    return {
        "require_registry_current": bool(payload.get("require_registry_current", True)),
        "require_portal_current": bool(payload.get("require_portal_current", True)),
        "require_transparency_current": bool(payload.get("require_transparency_current", True)),
        "require_acknowledgement_current": bool(payload.get("require_acknowledgement_current", False)),
        "require_release_signoff": bool(payload.get("require_release_signoff", True)),
        "require_distribution_signed": bool(payload.get("require_distribution_signed", False)),
        "require_submission_accepted": bool(payload.get("require_submission_accepted", False)),
        "require_submission_evidence_signed": bool(payload.get("require_submission_evidence_signed", False)),
        "require_operations_signed": bool(payload.get("require_operations_signed", False)),
        "require_operations_audit_verified": bool(payload.get("require_operations_audit_verified", False)),
        "require_operations_reviewer_pack_verified": bool(payload.get("require_operations_reviewer_pack_verified", False)),
    }


def _findings_from_source(source: ImplementationDocument) -> tuple[list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
    blockers: list[ImplementationDocument] = []
    warnings: list[ImplementationDocument] = []
    checks: list[ImplementationDocument] = []
    policy = _as_document(source.get("policy"))
    packages = source.get("public_package_fingerprints", []) if isinstance(source.get("public_package_fingerprints"), list) else []
    portfolio_count = int(source.get("portfolio_count") or 0)
    if portfolio_count == 0:
        warnings.append(_finding("no_portfolios", "warning", "No Portfolio Governance public evidence is selected."))
    required = {
        "registry": bool(policy.get("require_registry_current", True)),
        "portal": bool(policy.get("require_portal_current", True)),
        "transparency": bool(policy.get("require_transparency_current", True)),
        "transparency_acknowledgement": bool(policy.get("require_acknowledgement_current", False)),
    }
    for package_type, enabled in required.items():
        if not enabled:
            continue
        matching = [item for item in packages if isinstance(item, dict) and item.get("package_type") == package_type]
        if portfolio_count and len(matching) < portfolio_count:
            blockers.append(_finding(f"{package_type}_missing", "critical", f"{package_type} evidence is missing for one or more portfolios."))
        failed = [item for item in matching if item.get("verification_status") != "passed"]
        if failed:
            blockers.append(_finding(f"{package_type}_verification_failed", "critical", f"{package_type} verification is not passed."))
    for package_type in sorted(required):
        matching = [item for item in packages if isinstance(item, dict) and item.get("package_type") == package_type]
        ok = (not required[package_type]) or (len(matching) >= portfolio_count and all(item.get("verification_status") == "passed" for item in matching))
        checks.append({"check_id": f"ptc_{package_type}_coverage", "status": "passed" if ok else "failed", "severity": "blocking", "message": f"{package_type} coverage {'passed' if ok else 'failed'}."})
    delivery_required = {
        "release_signoff": bool(policy.get("require_release_signoff", True)),
        "distribution_signed": bool(policy.get("require_distribution_signed", False)),
        "submission_accepted": bool(policy.get("require_submission_accepted", False)),
        "submission_evidence_signed": bool(policy.get("require_submission_evidence_signed", False)),
        "operations_signed": bool(policy.get("require_operations_signed", False)),
        "operations_audit_verified": bool(policy.get("require_operations_audit_verified", False)),
        "operations_reviewer_pack_verified": bool(policy.get("require_operations_reviewer_pack_verified", False)),
    }
    readiness = source.get("delivery_readiness_matrix", []) if isinstance(source.get("delivery_readiness_matrix"), list) else []
    if delivery_required["release_signoff"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("release_signoff_status") not in {"signed", "force_signed"}]
        if failed:
            blockers.append(_finding("release_signoff_required", "critical", "One or more releases are missing Release Signoff."))
    if delivery_required["distribution_signed"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("distribution_status") not in {"ready"}]
        if failed:
            blockers.append(_finding("distribution_signed_required", "critical", "Distribution readiness is required but not complete."))
    if delivery_required["submission_accepted"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("submission_status") not in {"accepted"}]
        if failed:
            blockers.append(_finding("submission_accepted_required", "critical", "Submission accepted status is required but missing."))
    if delivery_required["submission_evidence_signed"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("submission_evidence_status") not in {"signed"}]
        if failed:
            blockers.append(_finding("submission_evidence_signed_required", "critical", "Submission Evidence signoff is required but missing."))
    if delivery_required["operations_signed"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("operations_status") not in {"signed", "force_signed"}]
        if failed:
            blockers.append(_finding("operations_signed_required", "critical", "Release Operations signoff is required but missing."))
    if delivery_required["operations_audit_verified"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("operations_audit_status") not in {"passed", "warning"}]
        if failed:
            blockers.append(_finding("operations_audit_required", "critical", "Release Operations Audit verification is required but missing."))
    if delivery_required["operations_reviewer_pack_verified"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("operations_reviewer_pack_status") not in {"passed", "warning"}]
        if failed:
            blockers.append(_finding("operations_reviewer_pack_required", "critical", "Release Operations Reviewer Pack verification is required but missing."))
    delivery_blocker_ids = {
        "release_signoff": "release_signoff_required",
        "distribution_signed": "distribution_signed_required",
        "submission_accepted": "submission_accepted_required",
        "submission_evidence_signed": "submission_evidence_signed_required",
        "operations_signed": "operations_signed_required",
        "operations_audit_verified": "operations_audit_required",
        "operations_reviewer_pack_verified": "operations_reviewer_pack_required",
    }
    for check_id, enabled in delivery_required.items():
        if not enabled:
            checks.append({"check_id": f"ptc_{check_id}", "status": "passed", "severity": "blocking", "message": f"{check_id} is not required."})
            continue
        failed = [item for item in blockers if str(item.get("check_id") or "") == delivery_blocker_ids.get(check_id)]
        checks.append({"check_id": f"ptc_{check_id}", "status": "failed" if failed else "passed", "severity": "blocking", "message": f"{check_id} {'failed' if failed else 'passed'}."})
    checks.append({"check_id": "ptc_source_redaction", "status": "passed" if _redaction_summary(source)["status"] == "passed" else "failed", "severity": "blocking", "message": "Public Trust Center source redaction scan completed."})
    if _redaction_summary(source)["status"] != "passed":
        blockers.append(_finding("source_redaction", "critical", "Public Trust Center source contains sensitive values."))
    return blockers, warnings, checks


def _release_readiness(source: ImplementationDocument) -> list[ImplementationDocument]:
    rows = []
    for item in source.get("releases", []) if isinstance(source.get("releases"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "release_id": item.get("release_id"),
                "name": item.get("name"),
                "status": item.get("status"),
                "signoff_status": item.get("signoff_status"),
                "track_count": item.get("track_count", 0),
                "readiness": "ready" if item.get("signoff_status") in {"signed", "force_signed"} else "review_needed",
                "zip_sha256": item.get("zip_sha256"),
            }
        )
    return sorted(rows, key=lambda item: str(item.get("release_id") or ""))


def _delivery_readiness(source: ImplementationDocument) -> list[ImplementationDocument]:
    return sorted([dict(item) for item in source.get("delivery_readiness_matrix", []) if isinstance(item, dict)], key=lambda item: str(item.get("release_id") or ""))


def _portfolio_readiness(source: ImplementationDocument) -> list[ImplementationDocument]:
    rows = []
    for item in source.get("portfolios", []) if isinstance(source.get("portfolios"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append({"portfolio_id": item.get("portfolio_id"), "status": item.get("status"), "profile": item.get("profile"), "public_package_status": item.get("public_package_status")})
    return sorted(rows, key=lambda item: str(item.get("portfolio_id") or ""))

















def _verification_sidecar_document(package: ImplementationDocument, verification_report: ImplementationDocument) -> ImplementationDocument:
    verification_hash = _verification_hash(verification_report)
    doc = {
        "schema_version": PTC_SCHEMA_VERSION,
        "package_type": "musicforge_public_trust_center_package_verification_summary",
        "sidecar_path": _verification_sidecar_path(str(package.get("portfolio_id") or ""), str(package.get("profile") or "public_summary"), str(package.get("package_type") or "")),
        "portfolio_id": package.get("portfolio_id"),
        "profile": package.get("profile"),
        "public_package_type": package.get("package_type"),
        "package": {
            "portfolio_id": package.get("portfolio_id"),
            "profile": package.get("profile"),
            "package_type": package.get("package_type"),
            "zip_sha256": package.get("zip_sha256"),
            "zip_size_bytes": package.get("zip_size_bytes"),
            "manifest_hash": package.get("manifest_hash"),
            "verification_hash": verification_hash,
            "verification_status": _verification_current_status(verification_report, package.get("zip_sha256"), package.get("zip_size_bytes"), package.get("manifest_hash")),
            "verification_report_hash": verification_hash,
            "verification_report_status": verification_report.get("status") or "missing",
        },
        "verification": {
            "verification_report_hash": verification_hash,
            "verification_report_status": verification_report.get("status") or "missing",
            "zip_sha256": verification_report.get("zip_sha256"),
            "zip_size_bytes": verification_report.get("zip_size_bytes"),
            "manifest_hash": verification_report.get("manifest_hash"),
            "blocker_count": len(verification_report.get("blockers", []) if isinstance(verification_report.get("blockers"), list) else []),
            "warning_count": len(verification_report.get("warnings", []) if isinstance(verification_report.get("warnings"), list) else []),
        },
    }
    doc["summary_hash"] = stable_hash({"package": doc["package"], "verification": doc["verification"]})
    return _sanitize_public_metadata(doc)








from song_agent.domains.trust import v142_ptc_readiness_2 as _v142_ptc_readiness_2
from song_agent.domains.trust.v142_ptc_readiness_2 import (
    _delivery_sidecar_document,
    _delivery_fingerprint_sidecar_document,
    _delivery_bottom_fingerprints,
    _delivery_sidecar_evidence,
    _verification_sidecar_path,
    _delivery_sidecar_path,
    _delivery_fingerprint_sidecar_path,
    _risk_register,
    _delivery_risk_register,
    _delivery_readiness_matrix_from_parts,
    _delivery_risk_register_from_matrix,
    _delivery_risks_for_row,
    _has_blocking_delivery_status,
    _distribution_status,
    _submission_status,
    _submission_evidence_status,
    _operations_status,
    _operations_audit_status,
    _operations_reviewer_pack_status,
    _package_status_from_fingerprints,
    _finding,
    _aggregate_status,
    _domain_from_summary,
    _domain_not_configured_row,
    _latest_feedback_status,
    _nested_status,
    _stable_hash_without_zip,
    _package_report_current_status,
    _state_row,
    _manifest_state,
    _zip_manifest_state,
    _page_record,
    _file_record,
    _zip_entries,
    _write_zip,
    _read_json_default,
    _read_zip_json,
    _write_json,
)
from song_agent.domains.trust import v142_ptc_evidence as _v142_ptc_evidence
from song_agent.domains.trust.v142_ptc_evidence import (
    _sanitize_public_metadata,
    _sha256,
    _verification_hash,
    _verification_current_status,
    _ensure_within,
    _safe_id,
    _redaction_summary,
    _write_readme,
)


























































































































_v142_ptc_readiness.bind_globals(globals())
_v142_ptc_evidence_2.bind_globals(globals())
_v142_ptc_lifecycle.bind_globals(globals())

_v142_ptc_readiness_2.bind_globals(globals())
_v142_ptc_evidence.bind_globals(globals())
