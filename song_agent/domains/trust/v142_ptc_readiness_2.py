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
from song_agent.domains.trust.v142_ptc_readiness import PublicTrustCenterStoreReadinessMixin
from song_agent.domains.trust import v142_ptc_readiness as _v142_ptc_readiness
from song_agent.domains.trust.v142_ptc_evidence_2 import PublicTrustCenterStoreEvidenceMixin
from song_agent.domains.trust import v142_ptc_evidence_2 as _v142_ptc_evidence_2
from song_agent.domains.trust.v142_ptc_lifecycle import PublicTrustCenterStoreLifecycleMixin
from song_agent.domains.trust import v142_ptc_lifecycle as _v142_ptc_lifecycle

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

_safe_id = _make_deferred_global('_safe_id')
_sanitize_public_metadata = _make_deferred_global('_sanitize_public_metadata')
_sha256 = _make_deferred_global('_sha256')

def bind_globals(namespace: dict[str, object]) -> None:
    global _safe_id, _sanitize_public_metadata, _sha256
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize_public_metadata = namespace.get('_sanitize_public_metadata', _sanitize_public_metadata)
    _sha256 = namespace.get('_sha256', _sha256)
    _bind_deferred_defaults(namespace)


PTC_SCHEMA_VERSION = 1
PTC_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_report"
PTC_CONFIG_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
PTC_DELIVERY_DOMAINS = ("release", "distribution", "submission", "submission_evidence", "operations", "operations_audit", "operations_reviewer_pack")




def _delivery_sidecar_document(domain: str, item: DomainDocument, *, fingerprint_path: str | None = None, fingerprint_hash: str | None = None) -> DomainDocument:
    summary = _delivery_summary_from_item(domain, item)
    payload = _delivery_public_payload(domain, item)
    evidence = _delivery_sidecar_evidence(domain, item, payload)
    if fingerprint_path:
        summary["fingerprint_sidecar_path"] = fingerprint_path
    if fingerprint_hash:
        summary["fingerprint_sidecar_hash"] = fingerprint_hash
    doc = {
        "schema_version": PTC_SCHEMA_VERSION,
        "package_type": "musicforge_public_trust_center_delivery_verification_summary",
        "sidecar_path": _delivery_sidecar_path(domain, str(item.get("release_id") or ""), str(item.get("target_id") or item.get("submission_id") or item.get("release_id") or "summary")),
        "release_id": item.get("release_id"),
        "domain": domain,
        "entity_id": summary.get("entity_id"),
        "fingerprint_sidecar_path": fingerprint_path,
        "fingerprint_sidecar_hash": fingerprint_hash,
        "summary": summary,
        "payload": payload,
        "evidence": evidence,
        "source_hash": stable_hash(item),
    }
    doc["summary_hash"] = stable_hash({"summary": summary, "payload": payload, "evidence": evidence})
    return _sanitize_public_metadata(doc)

def _delivery_fingerprint_sidecar_document(domain: str, item: DomainDocument, sidecar_path: str) -> DomainDocument:
    payload = _delivery_public_payload(domain, item)
    fingerprints = _delivery_bottom_fingerprints(domain, item)
    doc = {
        "schema_version": PTC_SCHEMA_VERSION,
        "package_type": "musicforge_public_trust_center_delivery_fingerprint_summary",
        "sidecar_path": sidecar_path,
        "release_id": item.get("release_id"),
        "domain": domain,
        "entity_id": str(item.get("target_id") or item.get("submission_id") or item.get("release_id") or ""),
        "payload": payload,
        "payload_hash": stable_hash(payload),
        "fingerprints": fingerprints,
    }
    doc["fingerprint_hash"] = stable_hash({"payload_hash": doc["payload_hash"], "fingerprints": fingerprints})
    return _sanitize_public_metadata(doc)

def _delivery_bottom_fingerprints(domain: str, item: DomainDocument) -> DomainDocument:
    keys = {
        "release_id",
        "target_id",
        "submission_id",
        "package_id",
        "signoff_status",
        "signoff_hash",
        "release_signoff_status",
        "release_zip_status",
        "zip_sha256",
        "zip_size_bytes",
        "export_manifest_hash",
        "package_zip_status",
        "package_zip_sha256",
        "package_zip_size_bytes",
        "manifest_hash",
        "verification_status",
        "verification_hash",
        "verification_report_status",
        "report_status",
        "report_hash",
        "operations_report_status",
        "operations_report_hash",
        "operations_source_hash",
        "operations_signoff_status",
        "operations_signoff_hash",
        "operations_archive_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "runbook_status",
        "fingerprint_hash",
    }
    return {"domain": domain, **{key: item.get(key) for key in sorted(keys) if key in item}}

def _delivery_sidecar_evidence(domain: str, item: DomainDocument, payload: DomainDocument) -> DomainDocument:
    evidence_keys = {
        "release_id",
        "target_id",
        "submission_id",
        "package_id",
        "status",
        "signoff_status",
        "signoff_hash",
        "release_signoff_status",
        "release_zip_status",
        "package_zip_status",
        "package_zip_sha256",
        "package_zip_size_bytes",
        "manifest_hash",
        "verification_status",
        "verification_hash",
        "verification_report_status",
        "operations_report_status",
        "operations_report_hash",
        "operations_source_hash",
        "operations_signoff_status",
        "operations_signoff_hash",
        "operations_archive_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "readiness",
        "risk_count",
        "distribution_status",
        "submission_status",
        "submission_evidence_status",
        "operations_status",
        "portfolio_public_proof_status",
        "fingerprint_hash",
    }
    evidence: DomainDocument = {
        "domain": domain,
        "payload": payload,
        "payload_hash": stable_hash(payload),
        "store_snapshot_hash": stable_hash({key: item.get(key) for key in sorted(evidence_keys) if key in item}),
    }
    for key in sorted(evidence_keys):
        if key in item:
            evidence[key] = item.get(key)
    return evidence

def _verification_sidecar_path(portfolio_id: str, profile: str, package_type: str) -> str:
    parts = [_safe_id(portfolio_id), _safe_id(profile or "public_summary"), _safe_id(package_type or "unknown")]
    return "package-verification-summaries/" + "__".join(parts) + ".json"

def _delivery_sidecar_path(domain: str, release_id: str, entity_id: str) -> str:
    parts = [_safe_id(release_id), _safe_id(domain or "delivery"), _safe_id(entity_id or "summary")]
    return "delivery-verification-summaries/" + "__".join(parts) + ".json"

def _delivery_fingerprint_sidecar_path(domain: str, release_id: str, entity_id: str) -> str:
    parts = [_safe_id(release_id), _safe_id(domain or "delivery"), _safe_id(entity_id or "summary")]
    return "delivery-fingerprint-summaries/" + "__".join(parts) + ".json"

def _risk_register(source: DomainDocument, blockers: list[DomainDocument], warnings: list[DomainDocument]) -> list[DomainDocument]:
    risks: list[DomainDocument] = []
    for index, item in enumerate(blockers, start=1):
        risks.append({"risk_id": f"ptc-risk_{index:03d}", "severity": "critical", "category": item.get("check_id"), "title": item.get("message"), "source": "blocker"})
    offset = len(risks)
    for index, item in enumerate(warnings, start=1):
        risks.append({"risk_id": f"ptc-risk_{offset + index:03d}", "severity": "warning", "category": item.get("check_id"), "title": item.get("message"), "source": "warning"})
    if not risks and int(source.get("portfolio_count") or 0) > 0:
        risks.append({"risk_id": "ptc-risk_000", "severity": "info", "category": "ready", "title": "Public trust evidence is current.", "source": "system"})
    return risks

def _delivery_risk_register(source: DomainDocument) -> list[DomainDocument]:
    return sorted([dict(item) for item in source.get("delivery_risk_register", []) if isinstance(item, dict)], key=lambda item: str(item.get("risk_id") or ""))

def _delivery_readiness_matrix_from_parts(
    releases: list[DomainDocument],
    portfolios: list[DomainDocument],
    distribution: list[DomainDocument],
    submissions: list[DomainDocument],
    submission_evidence: list[DomainDocument],
    operations: list[DomainDocument],
) -> list[DomainDocument]:
    portfolio_status = _aggregate_status([item.get("public_package_status") for item in portfolios if isinstance(item, dict)])
    rows: list[DomainDocument] = []
    for release in releases:
        if not isinstance(release, dict):
            continue
        release_id = str(release.get("release_id") or "")
        dist_rows = [item for item in distribution if isinstance(item, dict) and item.get("release_id") == release_id]
        sub_rows = [item for item in submissions if isinstance(item, dict) and item.get("release_id") == release_id]
        evidence_rows = [item for item in submission_evidence if isinstance(item, dict) and item.get("release_id") == release_id]
        ops_rows = [item for item in operations if isinstance(item, dict) and item.get("release_id") == release_id]
        row = {
            "release_id": release_id,
            "name": release.get("name"),
            "status": release.get("status"),
            "release_signoff_status": release.get("signoff_status") or "missing",
            "release_zip_status": "exists" if release.get("zip_sha256") else "missing",
            "distribution_status": _distribution_status(dist_rows),
            "submission_status": _submission_status(sub_rows),
            "submission_evidence_status": _submission_evidence_status(evidence_rows),
            "operations_status": _operations_status(ops_rows),
            "operations_audit_status": _operations_audit_status(ops_rows),
            "operations_reviewer_pack_status": _operations_reviewer_pack_status(ops_rows),
            "portfolio_public_proof_status": portfolio_status,
        }
        risk_count = len(_delivery_risks_for_row(row))
        row["risk_count"] = risk_count
        row["readiness"] = "ready" if risk_count == 0 and row["release_signoff_status"] in {"signed", "force_signed"} else "blocked" if _has_blocking_delivery_status(row) else "review_needed"
        row["fingerprint_hash"] = stable_hash(row)
        rows.append(_sanitize_public_metadata(row))
    return sorted(rows, key=lambda item: str(item.get("release_id") or ""))

def _delivery_risk_register_from_matrix(rows: list[DomainDocument]) -> list[DomainDocument]:
    risks: list[DomainDocument] = []
    for row in rows:
        risks.extend(_delivery_risks_for_row(row))
    if not risks and rows:
        risks.append({"risk_id": "ptc-delivery-risk-000000", "release_id": None, "domain": "delivery", "severity": "info", "status": "closed", "title": "Delivery evidence has no critical gaps.", "public_safe_detail": "All selected Release delivery summaries are ready or non-required."})
    for index, risk in enumerate(risks, start=1):
        risk["risk_id"] = f"ptc-delivery-risk-{index:06d}"
    return risks

def _delivery_risks_for_row(row: DomainDocument) -> list[DomainDocument]:
    release_id = row.get("release_id")
    checks = [
        ("release", row.get("release_signoff_status") in {"signed", "force_signed"}, "Release Signoff is missing."),
        ("release_zip", row.get("release_zip_status") == "exists", "Release ZIP is missing."),
        ("distribution", row.get("distribution_status") in {"ready", "not_configured"}, "Distribution package is not fully signed and verified."),
        ("submission", row.get("submission_status") in {"accepted", "not_configured", "missing"}, "Submission is not accepted."),
        ("submission_evidence", row.get("submission_evidence_status") in {"signed", "not_configured", "missing"}, "Submission Evidence Archive is not signed."),
        ("operations", row.get("operations_status") in {"signed", "force_signed", "not_configured", "missing"}, "Release Operations is not signed."),
    ]
    risks: list[DomainDocument] = []
    for domain, ok, message in checks:
        if ok:
            continue
        risks.append({"release_id": release_id, "domain": domain, "severity": "critical", "status": "open", "title": message, "public_safe_detail": message})
    return risks

def _has_blocking_delivery_status(row: DomainDocument) -> bool:
    return any(risk.get("severity") == "critical" for risk in _delivery_risks_for_row(row))

def _distribution_status(rows: list[DomainDocument]) -> str:
    if not rows:
        return "missing"
    if all(item.get("status") == "not_configured" for item in rows):
        return "not_configured"
    existing = [item for item in rows if item.get("target_id")]
    if not existing:
        return "missing"
    if any(item.get("verification_status") == "failed" for item in existing):
        return "failed"
    ready = [item for item in existing if item.get("signoff_status") in {"signed", "force_signed"} and item.get("verification_status") in {"passed", "warning"}]
    return "ready" if len(ready) == len(existing) else "partial" if ready else "missing"

def _submission_status(rows: list[DomainDocument]) -> str:
    if not rows:
        return "missing"
    if all(item.get("status") == "not_configured" for item in rows):
        return "not_configured"
    existing = [item for item in rows if item.get("submission_id")]
    if not existing:
        return "missing"
    if any(item.get("verification_status") == "failed" for item in existing):
        return "failed"
    if any(item.get("status") == "accepted" or int(item.get("accepted_count") or 0) > 0 for item in existing):
        return "accepted"
    if any(item.get("status") in {"submitted", "feedback_received", "needs_changes", "signed"} for item in existing):
        return "submitted"
    return "partial"

def _submission_evidence_status(rows: list[DomainDocument]) -> str:
    if not rows:
        return "missing"
    if all(item.get("status") == "not_configured" for item in rows):
        return "not_configured"
    existing = [item for item in rows if item.get("submission_id")]
    if not existing:
        return "missing"
    if any(item.get("verification_status") == "failed" or item.get("report_status") == "failed" for item in existing):
        return "failed"
    if any(item.get("signoff_status") in {"signed", "force_signed"} and item.get("verification_status") in {"passed", "warning"} for item in existing):
        return "signed"
    return "missing"

def _operations_status(rows: list[DomainDocument]) -> str:
    if not rows:
        return "missing"
    if all(item.get("status") == "not_configured" for item in rows):
        return "not_configured"
    first = rows[0]
    if first.get("operations_report_status") == "failed":
        return "failed"
    status = first.get("operations_signoff_status") or "missing"
    return status if status in {"signed", "force_signed"} else "unsigned" if first.get("operations_report_status") not in {"missing", None} else "missing"

def _operations_audit_status(rows: list[DomainDocument]) -> str:
    if not rows:
        return "missing"
    status = rows[0].get("operations_audit_status") or "missing"
    return status

def _operations_reviewer_pack_status(rows: list[DomainDocument]) -> str:
    if not rows:
        return "missing"
    status = rows[0].get("operations_reviewer_pack_status") or "missing"
    return status

def _package_status_from_fingerprints(packages: list[DomainDocument], package_type: str) -> str:
    matches = [item for item in packages if item.get("package_type") == package_type]
    if not matches:
        return "missing"
    return _aggregate_status([item.get("verification_status") for item in matches])

def _finding(check_id: str, severity: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": severity, "message": message}

def _aggregate_status(statuses: list[object]) -> str:
    values = [str(item or "missing") for item in statuses]
    if not values:
        return "missing"
    if any(item == "failed" for item in values):
        return "failed"
    if any(item == "missing" for item in values):
        return "missing"
    if any(item == "warning" for item in values):
        return "warning"
    return "passed"

def _domain_from_summary(item: DomainDocument) -> str | None:
    if item.get("target_id") is not None:
        return "distribution"
    if item.get("submission_id") is not None and ("report_status" in item or "attachment_count" in item):
        return "submission_evidence"
    if item.get("submission_id") is not None:
        return "submission"
    if "operations_report_status" in item or "package_fingerprints" in item:
        return "operations"
    if "release_signoff_status" in item or "distribution_status" in item:
        return "release"
    return None

def _domain_not_configured_row(domain: str, release_id: str, **extra: object) -> DomainDocument:
    row = {"release_id": release_id, "domain": domain, "status": "not_configured", "verification_status": "not_configured", **extra}
    row["fingerprint_hash"] = stable_hash(row)
    return row

def _latest_feedback_status(items: object) -> str:
    statuses = [str(getattr(item, "status", "") or "") for item in items]
    if any(status == "accepted" for status in statuses):
        return "accepted"
    if any(status == "needs_changes" for status in statuses):
        return "needs_changes"
    if any(status == "feedback_received" for status in statuses):
        return "feedback_received"
    return "none"

def _nested_status(payload: DomainDocument, path: tuple[str, ...], *, default: str = "missing") -> str:
    value: object = payload
    for part in path:
        if not isinstance(value, dict):
            return default
        value = value.get(part)
    return str(value or default)

def _stable_hash_without_zip(payload: DomainDocument) -> str | None:
    if not payload:
        return None
    return stable_hash({key: value for key, value in payload.items() if key != "zip"})

def _package_report_current_status(report: DomainDocument, zip_path: Path | None, manifest: DomainDocument) -> str:
    if not report:
        return "missing"
    if report.get("status") == "failed":
        return "failed"
    if zip_path is not None and zip_path.exists():
        current_sha = _sha256(zip_path)
        reported_sha = (_as_document(report.get("input"))).get("sha256") or report.get("zip_sha256")
        if reported_sha and current_sha and str(reported_sha) != str(current_sha):
            return "stale"
        current_size = zip_path.stat().st_size
        reported_size = (_as_document(report.get("input"))).get("size_bytes") or report.get("zip_size_bytes")
        if reported_size is not None and int(reported_size or 0) != int(current_size):
            return "stale"
    elif zip_path is not None:
        return "missing"
    manifest_hash = manifest.get("integrity_hash") or _stable_hash_without_zip(manifest)
    reported_manifest = report.get("manifest_hash")
    if reported_manifest and manifest_hash and str(reported_manifest) != str(manifest_hash):
        return "stale"
    status = str(report.get("status") or "missing")
    return status if status else "missing"

def _state_row(report: DomainDocument) -> dict[str, str]:
    summary = _as_document(report.get("summary"))
    return {"source_hash": str(report.get("source_hash") or ""), "report_integrity_hash": str(report.get("integrity_hash") or ""), "public_package_count": str(summary.get("public_package_count") or 0)}

def _manifest_state(manifest: DomainDocument) -> dict[str, str]:
    return {"source_hash": str(manifest.get("source_hash") or ""), "report_integrity_hash": str((_as_document(manifest.get("trust_center_report"))).get("integrity_hash") or ""), "public_package_count": str(manifest.get("public_package_count") or 0)}

def _zip_manifest_state(zip_path: Path) -> dict[str, str]:
    manifest = _read_zip_json(zip_path, "trust-center-manifest.json")
    return _manifest_state(manifest)

def _page_record(root: Path, path: str, source_hash: object) -> DomainDocument:
    resolved = root / path
    return {"path": path, "content_hash": _sha256(resolved), "source_hash": source_hash}

def _file_record(root: Path, path: Path) -> DomainDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}

def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]

def _write_zip(zip_path: Path, export_dir: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = __import__("tempfile").mkstemp(prefix=f".{zip_path.name}.", suffix=".tmp", dir=str(zip_path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, arcname in _zip_entries(export_dir):
                archive.write(path, arcname)
        tmp_path.replace(zip_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

def _read_json_default(path: Path, *, default: DomainDocument | None = None) -> DomainDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return _document_or(value, dict(default or {}))

def _read_zip_json(zip_path: Path, entry: str) -> DomainDocument:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except Exception:
        return {}

def _write_json(path: Path, payload: DomainDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, _sanitize_public_metadata(payload))
