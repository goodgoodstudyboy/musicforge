# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib as hashlib
import json as json
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any, Callable as Callable

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_contracts import PTC_BLOCKED_KEYS as PTC_BLOCKED_KEYS, PTC_HTML_PAGES as PTC_HTML_PAGES, PTC_PACKAGE_TYPE as PTC_PACKAGE_TYPE, expected_public_trust_center_documents as expected_public_trust_center_documents, public_trust_center_manifest_hash as public_trust_center_manifest_hash, public_trust_center_report_hash as public_trust_center_report_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.v142_ptccv_readiness import _PublicTrustCenterVerifierReadinessMixin
from song_agent.domains.trust import v142_ptccv_readiness as _v142_ptccv_readiness
from song_agent.domains.trust.v142_ptccv_evidence import _PublicTrustCenterVerifierEvidenceMixin
from song_agent.domains.trust import v142_ptccv_evidence as _v142_ptccv_evidence



PTC_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 250
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "trust-center-manifest.json",
    "trust-center-report.json",
    "data/trust-center-data.json",
    "data/release-index.json",
    "data/portfolio-index.json",
    "data/package-index.json",
    "data/verification-index.json",
    "data/public-package-verification-index.json",
    "data/risk-register.json",
    "data/transparency-index.json",
    "data/acknowledgement-index.json",
    "data/delivery-index.json",
    "data/distribution-index.json",
    "data/submission-index.json",
    "data/submission-evidence-index.json",
    "data/operations-index.json",
    "data/operations-package-index.json",
    "data/readiness-matrix.json",
    "data/delivery-risk-register.json",
    "data/delivery-verification-index.json",
    "index.html",
    "releases.html",
    "portfolios.html",
    "delivery.html",
    "distribution.html",
    "submissions.html",
    "operations.html",
    "evidence.html",
    "risk.html",
    "verify.html",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"trust-center-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
INLINE_EVENT_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
VERIFIER_BLOCKED_KEYS = PTC_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_public_trust_center_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_release_readiness: bool = False,
    require_public_attestation: bool = False,
    require_registry_current: bool = False,
    require_portal_current: bool = False,
    require_transparency_current: bool = False,
    require_acknowledgement_current: bool = False,
    require_delivery_readiness: bool = False,
    require_distribution_ready: bool = False,
    require_submission_accepted: bool = False,
    require_submission_evidence: bool = False,
    require_operations_signed: bool = False,
    require_operations_audit: bool = False,
    require_operations_reviewer_pack: bool = False,
    require_acceptance_board_signoff: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
    delivery_anchor_path: Path | str | None = None,
    anchor_registry_path: Path | str | None = None,
    anchor_transparency_path: Path | str | None = None,
    anchor_checkpoint_path: Path | str | None = None,
    acceptance_board_signoff_archive_path: Path | str | None = None,
    acceptance_board_path: Path | str | None = None,
    acceptance_board_verification_report_path: Path | str | None = None,
    distribution_kit_path: Path | str | None = None,
    accepted_evidence_dir: Path | str | None = None,
    require_anchor_registry_current: bool = False,
    require_anchor_published: bool = False,
    require_anchor_not_revoked: bool = False,
    require_anchor_transparency_current: bool = False,
    require_anchor_checkpoint: bool = False,
    _acceptance_board_signoff_verifier: Callable[..., DomainDocument] | None = None,
) -> DomainDocument:
    verifier = _PublicTrustCenterVerifier(
        Path(zip_path),
        strict=strict,
        require_release_readiness=require_release_readiness,
        require_public_attestation=require_public_attestation,
        require_registry_current=require_registry_current,
        require_portal_current=require_portal_current,
        require_transparency_current=require_transparency_current,
        require_acknowledgement_current=require_acknowledgement_current,
        require_delivery_readiness=require_delivery_readiness,
        require_distribution_ready=require_distribution_ready,
        require_submission_accepted=require_submission_accepted,
        require_submission_evidence=require_submission_evidence,
        require_operations_signed=require_operations_signed,
        require_operations_audit=require_operations_audit,
        require_operations_reviewer_pack=require_operations_reviewer_pack,
        require_acceptance_board_signoff=require_acceptance_board_signoff,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
        delivery_anchor_path=Path(delivery_anchor_path) if delivery_anchor_path is not None else None,
        anchor_registry_path=Path(anchor_registry_path) if anchor_registry_path is not None else None,
        anchor_transparency_path=Path(anchor_transparency_path) if anchor_transparency_path is not None else None,
        anchor_checkpoint_path=Path(anchor_checkpoint_path) if anchor_checkpoint_path is not None else None,
        acceptance_board_signoff_archive_path=Path(acceptance_board_signoff_archive_path) if acceptance_board_signoff_archive_path is not None else None,
        acceptance_board_path=Path(acceptance_board_path) if acceptance_board_path is not None else None,
        acceptance_board_verification_report_path=Path(acceptance_board_verification_report_path) if acceptance_board_verification_report_path is not None else None,
        distribution_kit_path=Path(distribution_kit_path) if distribution_kit_path is not None else None,
        accepted_evidence_dir=Path(accepted_evidence_dir) if accepted_evidence_dir is not None else None,
        require_anchor_registry_current=require_anchor_registry_current,
        require_anchor_published=require_anchor_published,
        require_anchor_not_revoked=require_anchor_not_revoked,
        require_anchor_transparency_current=require_anchor_transparency_current,
        require_anchor_checkpoint=require_anchor_checkpoint,
        acceptance_board_signoff_verifier=_acceptance_board_signoff_verifier,
    )
    return verifier.run()


def write_public_trust_center_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_verification_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Public Trust Center verification")
    print(f"status: {report.get('status')}")
    print(f"center: {summary.get('center_id') or 'unknown'}")
    print(f"readiness: {summary.get('readiness') or 'unknown'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")
    print(f"warnings: {len(_as_list(report.get('warnings')))}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        rows = _as_list(report.get(key))
        if not rows:
            continue
        print(f"{label}:")
        for item in rows[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def public_trust_center_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0


class _PublicTrustCenterVerifier(_PublicTrustCenterVerifierReadinessMixin, _PublicTrustCenterVerifierEvidenceMixin):
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_release_readiness: bool,
        require_public_attestation: bool,
        require_registry_current: bool,
        require_portal_current: bool,
        require_transparency_current: bool,
        require_acknowledgement_current: bool,
        require_delivery_readiness: bool,
        require_distribution_ready: bool,
        require_submission_accepted: bool,
        require_submission_evidence: bool,
        require_operations_signed: bool,
        require_operations_audit: bool,
        require_operations_reviewer_pack: bool,
        require_acceptance_board_signoff: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
        delivery_anchor_path: Path | None,
        anchor_registry_path: Path | None,
        anchor_transparency_path: Path | None,
        anchor_checkpoint_path: Path | None,
        acceptance_board_signoff_archive_path: Path | None,
        acceptance_board_path: Path | None,
        acceptance_board_verification_report_path: Path | None,
        distribution_kit_path: Path | None,
        accepted_evidence_dir: Path | None,
        require_anchor_registry_current: bool,
        require_anchor_published: bool,
        require_anchor_not_revoked: bool,
        require_anchor_transparency_current: bool,
        require_anchor_checkpoint: bool,
        acceptance_board_signoff_verifier: Callable[..., ImplementationDocument] | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_release_readiness = require_release_readiness
        self.require_public_attestation = require_public_attestation
        self.require_registry_current = require_registry_current
        self.require_portal_current = require_portal_current
        self.require_transparency_current = require_transparency_current
        self.require_acknowledgement_current = require_acknowledgement_current
        self.require_delivery_readiness = require_delivery_readiness
        self.require_distribution_ready = require_distribution_ready
        self.require_submission_accepted = require_submission_accepted
        self.require_submission_evidence = require_submission_evidence
        self.require_operations_signed = require_operations_signed
        self.require_operations_audit = require_operations_audit
        self.require_operations_reviewer_pack = require_operations_reviewer_pack
        self.require_acceptance_board_signoff = require_acceptance_board_signoff
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.delivery_anchor_path = delivery_anchor_path
        self.anchor_registry_path = anchor_registry_path
        self.anchor_transparency_path = anchor_transparency_path
        self.anchor_checkpoint_path = anchor_checkpoint_path
        self.acceptance_board_signoff_archive_path = acceptance_board_signoff_archive_path
        self.acceptance_board_path = acceptance_board_path
        self.acceptance_board_verification_report_path = acceptance_board_verification_report_path
        self.distribution_kit_path = distribution_kit_path
        self.accepted_evidence_dir = accepted_evidence_dir
        self.require_anchor_registry_current = require_anchor_registry_current
        self.require_anchor_published = require_anchor_published
        self.require_anchor_not_revoked = require_anchor_not_revoked
        self.require_anchor_transparency_current = require_anchor_transparency_current
        self.require_anchor_checkpoint = require_anchor_checkpoint
        self.acceptance_board_signoff_verifier = acceptance_board_signoff_verifier
        self.delivery_anchor_doc: ImplementationDocument = {}
        self.anchor_registry_verification: ImplementationDocument = {}
        self.anchor_transparency_verification: ImplementationDocument = {}
        self.checks: list[ImplementationDocument] = []
        self.files: list[ImplementationDocument] = []
        self.redaction_findings: list[ImplementationDocument] = []
        self.manifest: ImplementationDocument = {}
        self.report_doc: ImplementationDocument = {}
        self.data_docs: dict[str, ImplementationDocument] = {}
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0





























def _summary_from_source(source: ImplementationDocument, blockers: list[ImplementationDocument], warnings: list[ImplementationDocument]) -> ImplementationDocument:
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


def _delivery_risk_register(source: ImplementationDocument) -> list[ImplementationDocument]:
    return sorted([dict(item) for item in source.get("delivery_risk_register", []) if isinstance(item, dict)], key=lambda item: str(item.get("risk_id") or ""))


def _portfolio_readiness(source: ImplementationDocument) -> list[ImplementationDocument]:
    rows = []
    for item in source.get("portfolios", []) if isinstance(source.get("portfolios"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append({"portfolio_id": item.get("portfolio_id"), "status": item.get("status"), "profile": item.get("profile"), "public_package_status": item.get("public_package_status")})
    return sorted(rows, key=lambda item: str(item.get("portfolio_id") or ""))


def _package_index(source: ImplementationDocument) -> list[ImplementationDocument]:
    return sorted([dict(item) for item in source.get("public_package_fingerprints", []) if isinstance(item, dict)], key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _verification_index(source: ImplementationDocument) -> list[ImplementationDocument]:
    return sorted([dict(item) for item in source.get("verification_fingerprints", []) if isinstance(item, dict)], key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _package_verification_sidecars(source: ImplementationDocument) -> list[ImplementationDocument]:
    packages = _package_index(source)
    verifications = {
        _fingerprint_key(item): dict(item)
        for item in source.get("verification_fingerprints", [])
        if isinstance(item, dict)
    }
    rows: list[ImplementationDocument] = []
    for package in packages:
        verification = verifications.get(_fingerprint_key(package), {})
        rows.append(
            {
                "portfolio_id": package.get("portfolio_id"),
                "profile": package.get("profile"),
                "package_type": package.get("package_type"),
                "zip_sha256": package.get("zip_sha256"),
                "zip_size_bytes": package.get("zip_size_bytes"),
                "manifest_hash": package.get("manifest_hash"),
                "verification_hash": package.get("verification_hash"),
                "verification_status": package.get("verification_status"),
                "verification_report_hash": verification.get("verification_hash") or package.get("verification_hash"),
                "verification_report_status": verification.get("verification_status") or package.get("verification_status"),
                "blocker_count": verification.get("blocker_count", 0),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _package_verification_index_from_independent_sidecars(source_hash: Any, sidecars: dict[str, ImplementationDocument]) -> ImplementationDocument:
    packages: list[ImplementationDocument] = []
    verifications: list[ImplementationDocument] = []
    rows = []
    for path, doc in sorted(sidecars.items()):
        if not isinstance(doc, dict):
            continue
        package = dict(_as_document(doc.get("package")))
        package["sidecar_path"] = path
        package["sidecar_hash"] = stable_hash(doc)
        packages.append(package)
        verification = _as_document(doc.get("verification"))
        verifications.append(
            {
                "portfolio_id": package.get("portfolio_id"),
                "profile": package.get("profile"),
                "package_type": package.get("package_type"),
                "verification_hash": verification.get("verification_report_hash"),
                "verification_status": verification.get("verification_report_status"),
                "verification_report_hash": verification.get("verification_report_hash"),
                "verification_report_status": verification.get("verification_report_status"),
                "blocker_count": verification.get("blocker_count", 0),
                "zip_sha256": verification.get("zip_sha256"),
                "zip_size_bytes": verification.get("zip_size_bytes"),
                "manifest_hash": verification.get("manifest_hash"),
                "sidecar_path": path,
                "sidecar_hash": stable_hash(doc),
            }
        )
        rows.append({"path": path, "hash": stable_hash(doc)})
    return {
        "source_hash": source_hash,
        "packages": sorted(packages, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type")), str(item.get("profile")))),
        "verifications": sorted(verifications, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type")), str(item.get("profile")))),
        "sidecars": rows,
    }


def _delivery_verification_index_from_independent_sidecars(source_hash: Any, sidecars: dict[str, ImplementationDocument], fingerprint_sidecars: dict[str, ImplementationDocument] | None = None) -> ImplementationDocument:
    summaries: list[ImplementationDocument] = []
    rows: list[ImplementationDocument] = []
    fingerprint_rows: list[ImplementationDocument] = []
    for path, doc in sorted(sidecars.items()):
        if not isinstance(doc, dict):
            continue
        summary = dict(_as_document(doc.get("summary")))
        summary["sidecar_path"] = path
        summary["sidecar_hash"] = stable_hash(doc)
        if doc.get("fingerprint_sidecar_path"):
            summary["fingerprint_sidecar_path"] = doc.get("fingerprint_sidecar_path")
            summary["fingerprint_sidecar_hash"] = doc.get("fingerprint_sidecar_hash")
        summaries.append(summary)
        rows.append({"path": path, "hash": stable_hash(doc)})
    for path, doc in sorted((fingerprint_sidecars or {}).items()):
        if isinstance(doc, dict):
            fingerprint_rows.append({"path": path, "hash": stable_hash(doc)})
    return {"source_hash": source_hash, "summaries": sorted(summaries, key=_delivery_summary_key), "sidecars": rows, "fingerprint_sidecars": fingerprint_rows}


def _verification_sidecars(source: ImplementationDocument) -> list[ImplementationDocument]:
    packages = {
        _fingerprint_key(item): dict(item)
        for item in source.get("public_package_fingerprints", [])
        if isinstance(item, dict)
    }
    rows: list[ImplementationDocument] = []
    for verification in _verification_index(source):
        package = packages.get(_fingerprint_key(verification), {})
        rows.append(
            {
                "portfolio_id": verification.get("portfolio_id"),
                "profile": verification.get("profile"),
                "package_type": verification.get("package_type"),
                "verification_hash": verification.get("verification_hash"),
                "verification_status": verification.get("verification_status"),
                "blocker_count": verification.get("blocker_count", 0),
                "zip_sha256": package.get("zip_sha256") or verification.get("zip_sha256"),
                "zip_size_bytes": package.get("zip_size_bytes") or verification.get("zip_size_bytes"),
                "manifest_hash": package.get("manifest_hash") or verification.get("manifest_hash"),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


from song_agent.domains.trust import v142_ptccv_readiness_2 as _v142_ptccv_readiness_2
from song_agent.domains.trust.v142_ptccv_readiness_2 import (
    _packages_from_sidecars,
    _verifications_from_sidecars,
    _delivery_payloads_from_sidecars,
    _delivery_payloads_from_fingerprint_sidecars,
    _delivery_anchor_rows_from_fingerprint_sidecars,
    _read_zip_json,
    _find_registry_current_entry,
    _delivery_payloads_from_data_docs,
    _delivery_public_payload,
    _delivery_summary_key,
    _delivery_payload_key,
    _fingerprint_key,
    _is_forbidden_public_entry,
    _counts,
    _sha256_file,
    _sha256_entry,
    _sha256_text,
    _contains_local_path,
    _normalize_newlines,
    _redaction_findings,
    _allowed_public_false_positive,
    _blocked_key_findings,
)












































_v142_ptccv_readiness.bind_globals(globals())
_v142_ptccv_evidence.bind_globals(globals())

_v142_ptccv_readiness_2.bind_globals(globals())
