from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document, document_or as _document_or
from typing import Any
from pathlib import Path

from song_agent.domains.legacy_documents import ImplementationDocument

import hashlib
import json
from song_agent.domains.studio.projectio import read_json
from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_contracts import ACCEPTED_EVIDENCE_BLOCKED_KEYS, accepted_evidence_hash, accepted_evidence_summary


def accepted_evidence_integrity_ok(evidence: dict[str, Any] | None) -> bool:
    data = _as_document(evidence)
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == accepted_evidence_hash(data)


def accepted_evidence_public_summary_from_portfolio_dir(portfolio_dir: Path, *, profile: str = "public_summary") -> dict[str, Any]:
    root = portfolio_dir / "governance-attestation-accepted-evidence"
    if profile != "public_summary":
        root = root / "profiles" / _safe_profile(profile)
    evidence = _read_json_default(root / "accepted-evidence.json", default={})
    if not evidence:
        return _missing_public_summary()
    if not accepted_evidence_integrity_ok(evidence):
        summary = accepted_evidence_summary(evidence)
        summary["status"] = "failed"
        summary["external_review_status"] = "failed"
        summary.setdefault("accepted_evidence_verification_status", "missing")
        summary.setdefault("accepted_evidence_verification_report_hash", None)
        return summary
    summary = accepted_evidence_summary(evidence)
    verification = _read_json_default(root / "accepted-evidence-verification-report.json", default={})
    verification_status = verification.get("status") or "missing"
    zip_path = root / "governance-attestation-accepted-evidence.zip"
    manifest = _read_json_default(root / "accepted-evidence-export" / "accepted-evidence-manifest.json", default={})
    current_zip_sha256 = _sha256(zip_path)
    current_manifest_hash = manifest.get("integrity_hash") if isinstance(manifest, dict) else None
    if verification_status == "passed" and (
        not current_zip_sha256
        or verification.get("zip_sha256") != current_zip_sha256
        or not current_manifest_hash
        or verification.get("manifest_hash") != current_manifest_hash
    ):
        verification_status = "failed"
    summary["accepted_evidence_verification_status"] = verification_status
    summary["accepted_evidence_zip_sha256"] = verification.get("zip_sha256")
    summary["accepted_evidence_zip_size_bytes"] = verification.get("zip_size_bytes")
    summary["accepted_evidence_manifest_hash"] = verification.get("manifest_hash")
    summary["accepted_evidence_verification_report_hash"] = stable_hash(verification) if verification else None
    return sanitize_metadata(summary, blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS)


def _missing_public_summary() -> ImplementationDocument:
    return {
        "status": "missing",
        "external_review_status": "missing",
        "accepted_evidence_id": None,
        "response_id": None,
        "reviewer_label": None,
        "reviewed_at": None,
        "verification_status": None,
        "source_hash": None,
        "current_entry_id": None,
        "current_certificate_id": None,
        "accepted_evidence_verification_status": "missing",
        "accepted_evidence_zip_sha256": None,
        "accepted_evidence_zip_size_bytes": None,
        "accepted_evidence_manifest_hash": None,
        "accepted_evidence_verification_report_hash": None,
    }


def accepted_evidence_verification_summary_from_portfolio_dir(portfolio_dir: Path, *, profile: str = "public_summary") -> dict[str, Any]:
    root = portfolio_dir / "governance-attestation-accepted-evidence"
    if profile != "public_summary":
        root = root / "profiles" / _safe_profile(profile)
    evidence = _read_json_default(root / "accepted-evidence.json", default={})
    verification = _read_json_default(root / "accepted-evidence-verification-report.json", default={})
    manifest = _read_json_default(root / "accepted-evidence-export" / "accepted-evidence-manifest.json", default={})
    public_summary = accepted_evidence_summary(evidence) if evidence else {"status": "missing", "external_review_status": "missing"}
    zip_path = root / "governance-attestation-accepted-evidence.zip"
    current_zip_sha256 = _sha256(zip_path)
    current_manifest_hash = manifest.get("integrity_hash") if isinstance(manifest, dict) else None
    verification_status = verification.get("status") or "missing"
    if verification_status == "passed" and (
        not current_zip_sha256
        or verification.get("zip_sha256") != current_zip_sha256
        or not current_manifest_hash
        or verification.get("manifest_hash") != current_manifest_hash
    ):
        verification_status = "failed"
    return sanitize_metadata(
        {
            "package_type": "release_portfolio_governance_attestation_accepted_evidence_verification_summary",
            "profile": profile,
            "accepted_evidence_id": evidence.get("accepted_evidence_id"),
            "accepted_evidence_source_hash": evidence.get("source_hash"),
            "accepted_evidence_status": public_summary.get("status"),
            "external_review_status": public_summary.get("external_review_status"),
            "response_id": public_summary.get("response_id"),
            "current_entry_id": public_summary.get("current_entry_id"),
            "current_certificate_id": public_summary.get("current_certificate_id"),
            "accepted_evidence_verification_status": verification_status,
            "accepted_evidence_zip_sha256": verification.get("zip_sha256"),
            "accepted_evidence_zip_size_bytes": verification.get("zip_size_bytes"),
            "accepted_evidence_manifest_hash": verification.get("manifest_hash"),
            "accepted_evidence_verification_report_hash": stable_hash(verification) if verification else None,
            "current_zip_sha256": current_zip_sha256,
            "current_manifest_hash": current_manifest_hash,
        },
        blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS,
    )


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return _document_or(value, dict(default or {}))


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_profile(profile: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(profile or "public_summary"))[:80] or "public_summary"
