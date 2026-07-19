# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, document_or as _document_or

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
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore as ReleasePortfolioAuditStore, portfolio_report_integrity_hash as portfolio_report_integrity_hash, portfolio_report_integrity_ok as portfolio_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance import ReleasePortfolioGovernanceStore as ReleasePortfolioGovernanceStore, queue_integrity_ok as queue_integrity_ok, queue_summary as queue_summary
from song_agent.domains.trust.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore as ReleasePortfolioGovernanceAuditStore, audit_report_integrity_hash as audit_report_integrity_hash, audit_report_integrity_ok as audit_report_integrity_ok, audit_summary as audit_summary
from song_agent.domains.trust.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore as ReleasePortfolioGovernanceFinalBoardStore, final_board_archive_manifest_integrity_ok as final_board_archive_manifest_integrity_ok, final_board_report_integrity_hash as final_board_report_integrity_hash, final_board_report_integrity_ok as final_board_report_integrity_ok, final_board_signoff_hash as final_board_signoff_hash, final_board_signoff_integrity_ok as final_board_signoff_integrity_ok, final_board_signoff_summary as final_board_signoff_summary, final_board_summary as final_board_summary
from song_agent.domains.trust.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore as ReleasePortfolioGovernanceReviewerPackStore, reviewer_pack_manifest_integrity_ok as reviewer_pack_manifest_integrity_ok, reviewer_pack_summary as reviewer_pack_summary, reviewer_report_integrity_hash as reviewer_report_integrity_hash, reviewer_report_integrity_ok as reviewer_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore as ReleasePortfolioGovernanceSignoffStore, governance_archive_manifest_integrity_ok as governance_archive_manifest_integrity_ok, governance_signoff_hash as governance_signoff_hash, governance_signoff_integrity_ok as governance_signoff_integrity_ok, governance_signoff_summary as governance_signoff_summary
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_evidence_vault_contracts import EVIDENCE_VAULT_BLOCKED_KEYS as EVIDENCE_VAULT_BLOCKED_KEYS, EVIDENCE_VAULT_INDEX_HASH_EXCLUDE_KEYS as EVIDENCE_VAULT_INDEX_HASH_EXCLUDE_KEYS, EVIDENCE_VAULT_MANIFEST_HASH_EXCLUDE_KEYS as EVIDENCE_VAULT_MANIFEST_HASH_EXCLUDE_KEYS, EVIDENCE_VAULT_PACKAGE_TYPE as EVIDENCE_VAULT_PACKAGE_TYPE, EVIDENCE_VAULT_REPORT_HASH_EXCLUDE_KEYS as EVIDENCE_VAULT_REPORT_HASH_EXCLUDE_KEYS, evidence_vault_chain_hash as evidence_vault_chain_hash, evidence_vault_manifest_hash as evidence_vault_manifest_hash, evidence_vault_package_index_hash as evidence_vault_package_index_hash, evidence_vault_report_integrity_hash as evidence_vault_report_integrity_hash, evidence_vault_verification_index_hash as evidence_vault_verification_index_hash, evidence_vault_verification_summary as evidence_vault_verification_summary
from song_agent.domains.trust.v142_rpgev_readiness import ReleasePortfolioGovernanceEvidenceVaultStoreReadinessMixin
from song_agent.domains.trust import v142_rpgev_readiness as _v142_rpgev_readiness
from song_agent.domains.trust.v142_rpgev_evidence import ReleasePortfolioGovernanceEvidenceVaultStoreEvidenceMixin
from song_agent.domains.trust import v142_rpgev_evidence as _v142_rpgev_evidence



EVIDENCE_VAULT_SCHEMA_VERSION = 1
EVIDENCE_VAULT_EXPORT_SCHEMA_VERSION = 1





SIGNED_STATUSES = {"signed", "force_signed"}


class ReleasePortfolioGovernanceEvidenceVaultError(ValueError):
    pass


class ReleasePortfolioGovernanceEvidenceVaultNotFoundError(ReleasePortfolioGovernanceEvidenceVaultError):
    pass


class ReleasePortfolioGovernanceEvidenceVaultStateError(ReleasePortfolioGovernanceEvidenceVaultError):
    pass


class ReleasePortfolioGovernanceEvidenceVaultStore(ReleasePortfolioGovernanceEvidenceVaultStoreReadinessMixin, ReleasePortfolioGovernanceEvidenceVaultStoreEvidenceMixin):
    def __init__(
        self,
        *,
        portfolio_store: ReleasePortfolioAuditStore,
        governance_store: ReleasePortfolioGovernanceStore,
        signoff_store: ReleasePortfolioGovernanceSignoffStore,
        audit_store: ReleasePortfolioGovernanceAuditStore,
        reviewer_pack_store: ReleasePortfolioGovernanceReviewerPackStore,
        final_board_store: ReleasePortfolioGovernanceFinalBoardStore,
    ) -> None:
        self.portfolio_store = portfolio_store
        self.governance_store = governance_store
        self.signoff_store = signoff_store
        self.audit_store = audit_store
        self.reviewer_pack_store = reviewer_pack_store
        self.final_board_store = final_board_store
        self.lock = threading.RLock()




























def build_package_index(*, portfolio_id: str, source_hash: str, packages: list[DomainDocument], generated_at: str) -> DomainDocument:
    items = [
        {
            "package_id": item.get("package_id"),
            "role": item.get("role"),
            "package_type": item.get("package_type"),
            "queue_id": item.get("queue_id"),
            "required": bool(item.get("required")),
            "vault_path": item.get("vault_path"),
            "sha256": item.get("sha256"),
            "size_bytes": item.get("size_bytes"),
            "manifest_hash": item.get("manifest_hash"),
            "verification_report_hash": item.get("verification_hash"),
            "verification_vault_path": item.get("verification_vault_path"),
            "verification_status": item.get("verification_status"),
            "current": _package_verification_current(item),
        }
        for item in packages
        if item.get("exists") or item.get("required")
    ]
    data = {"schema_version": EVIDENCE_VAULT_SCHEMA_VERSION, "portfolio_id": portfolio_id, "generated_at": generated_at, "source_hash": source_hash, "summary": {"package_count": len(items), "required_count": sum(1 for item in items if item.get("required"))}, "items": items}
    data["integrity_hash"] = evidence_vault_package_index_hash(data)
    return sanitize_metadata(data, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)


def build_verification_index(*, portfolio_id: str, source_hash: str, packages: list[DomainDocument], generated_at: str) -> DomainDocument:
    items = [
        {
            "package_id": item.get("package_id"),
            "role": item.get("role"),
            "queue_id": item.get("queue_id"),
            "required": bool(item.get("required")),
            "verification_vault_path": item.get("verification_vault_path"),
            "verification_hash": item.get("verification_hash"),
            "verification_status": item.get("verification_status"),
            "verification_zip_sha256": item.get("verification_zip_sha256"),
            "verification_zip_size_bytes": item.get("verification_zip_size_bytes"),
            "verification_manifest_hash": item.get("verification_manifest_hash"),
            "expected_zip_sha256": item.get("sha256"),
            "expected_zip_size_bytes": item.get("size_bytes"),
            "expected_manifest_hash": item.get("manifest_hash"),
            "current": _package_verification_current(item),
        }
        for item in packages
        if item.get("verification_exists") or item.get("required")
    ]
    data = {"schema_version": EVIDENCE_VAULT_SCHEMA_VERSION, "portfolio_id": portfolio_id, "generated_at": generated_at, "source_hash": source_hash, "summary": {"verification_count": len(items), "required_count": sum(1 for item in items if item.get("required"))}, "items": items}
    data["integrity_hash"] = evidence_vault_verification_index_hash(data)
    return sanitize_metadata(data, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)


def build_chain_of_custody(*, portfolio_id: str, source_hash: str, packages: list[DomainDocument], generated_at: str) -> DomainDocument:
    events = []
    for item in packages:
        events.append(
            {
                "event_type": "nested_package_captured",
                "package_id": item.get("package_id"),
                "role": item.get("role"),
                "queue_id": item.get("queue_id"),
                "required": bool(item.get("required")),
                "package_sha256": item.get("sha256"),
                "manifest_hash": item.get("manifest_hash"),
                "verification_hash": item.get("verification_hash"),
                "verification_status": item.get("verification_status"),
                "current": _package_verification_current(item),
            }
        )
    data = {"schema_version": EVIDENCE_VAULT_SCHEMA_VERSION, "portfolio_id": portfolio_id, "generated_at": generated_at, "source_hash": source_hash, "summary": {"event_count": len(events), "current_count": sum(1 for item in events if item.get("current"))}, "events": events}
    data["integrity_hash"] = evidence_vault_chain_hash(data)
    return sanitize_metadata(data, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)





def evidence_vault_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_vault_report_integrity_hash(data)





def evidence_vault_package_index_integrity_ok(index: DomainDocument | None) -> bool:
    data = _as_document(index)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_vault_package_index_hash(data)





def evidence_vault_verification_index_integrity_ok(index: DomainDocument | None) -> bool:
    data = _as_document(index)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_vault_verification_index_hash(data)





def evidence_vault_chain_integrity_ok(chain: DomainDocument | None) -> bool:
    data = _as_document(chain)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_vault_chain_hash(data)





def evidence_vault_manifest_integrity_ok(manifest: DomainDocument | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_vault_manifest_hash(data)


def evidence_vault_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    if not data:
        return {"status": "missing", "integrity_ok": False}
    summary = _as_document(data.get("summary"))
    return sanitize_metadata({"status": data.get("status"), "readiness": data.get("readiness"), "portfolio_id": data.get("portfolio_id"), "source_hash": data.get("source_hash"), "integrity_hash": data.get("integrity_hash"), "integrity_ok": evidence_vault_report_integrity_ok(data), **summary}, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)





def _package_verification_current(package: ImplementationDocument) -> bool:
    if not package.get("exists") or not package.get("manifest_exists") or not package.get("verification_exists"):
        return False
    if package.get("verification_status") != "passed":
        return False
    if not package.get("sha256") or package.get("verification_zip_sha256") != package.get("sha256"):
        return False
    if _int_or_none(package.get("verification_zip_size_bytes")) != _int_or_none(package.get("size_bytes")):
        return False
    if not package.get("manifest_hash") or package.get("verification_manifest_hash") != package.get("manifest_hash"):
        return False
    return True


def _nested_manifest_integrity_ok(package_type: str, manifest: ImplementationDocument) -> bool:
    if not manifest:
        return False
    if manifest.get("package_type") != package_type:
        return False
    if package_type == "release_portfolio_governance_final_board_archive":
        return final_board_archive_manifest_integrity_ok(manifest)
    if package_type == "release_portfolio_governance_reviewer_pack":
        return reviewer_pack_manifest_integrity_ok(manifest)
    if package_type == "release_portfolio_governance_audit":
        from song_agent.domains.trust.release_portfolio_governance_audit import audit_manifest_integrity_ok

        return audit_manifest_integrity_ok(manifest)
    if package_type == "release_portfolio_governance_archive":
        return governance_archive_manifest_integrity_ok(manifest)
    if package_type == "release_portfolio_governance_queue":
        from song_agent.domains.trust.release_portfolio_governance import governance_manifest_integrity_ok

        return governance_manifest_integrity_ok(manifest)
    return False


def _summary_from_source(source: ImplementationDocument, packages: list[ImplementationDocument], blockers: list[ImplementationDocument], warnings: list[ImplementationDocument]) -> ImplementationDocument:
    required = [item for item in packages if item.get("required")]
    current = [item for item in required if _package_verification_current(item)]
    return {
        "final_board_status": source.get("final_board_report_status"),
        "final_board_signoff_status": source.get("final_board_signoff_status"),
        "reviewer_pack_status": source.get("reviewer_report_status"),
        "governance_audit_status": source.get("governance_audit_report_status"),
        "signed_queue_count": int(source.get("signed_queue_count") or 0),
        "force_signed_queue_count": int(source.get("force_signed_queue_count") or 0),
        "nested_package_count": len(packages),
        "required_package_count": len(required),
        "current_required_package_count": len(current),
        "archive_package_count": sum(1 for item in packages if item.get("role") == "governance_archive"),
        "queue_package_count": sum(1 for item in packages if item.get("role") == "governance_queue"),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
    }


def _package_summaries(packages: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [
        {
            "package_id": item.get("package_id"),
            "role": item.get("role"),
            "package_type": item.get("package_type"),
            "queue_id": item.get("queue_id"),
            "required": bool(item.get("required")),
            "exists": bool(item.get("exists")),
            "manifest_hash": item.get("manifest_hash"),
            "sha256": item.get("sha256"),
            "size_bytes": item.get("size_bytes"),
            "verification_status": item.get("verification_status"),
            "verification_hash": item.get("verification_hash"),
            "current": _package_verification_current(item),
            "vault_path": item.get("vault_path"),
            "verification_vault_path": item.get("verification_vault_path"),
        }
        for item in packages
    ]


def _manifest_packages(packages: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [
        {
            "package_id": item.get("package_id"),
            "role": item.get("role"),
            "package_type": item.get("package_type"),
            "queue_id": item.get("queue_id"),
            "required": bool(item.get("required")),
            "path": item.get("vault_path"),
            "sha256": item.get("sha256"),
            "size_bytes": item.get("size_bytes"),
            "manifest_hash": item.get("manifest_hash"),
            "verification_path": item.get("verification_vault_path"),
            "verification_hash": item.get("verification_hash"),
            "verification_status": item.get("verification_status"),
            "verification_zip_sha256": item.get("verification_zip_sha256"),
            "verification_zip_size_bytes": item.get("verification_zip_size_bytes"),
            "verification_manifest_hash": item.get("verification_manifest_hash"),
            "current": _package_verification_current(item),
        }
        for item in packages
        if item.get("exists") or item.get("required")
    ]


def _package_source_row(package: ImplementationDocument) -> ImplementationDocument:
    return {
        "package_id": package.get("package_id"),
        "role": package.get("role"),
        "queue_id": package.get("queue_id"),
        "required": bool(package.get("required")),
        "sha256": package.get("sha256"),
        "size_bytes": package.get("size_bytes"),
        "manifest_hash": package.get("manifest_hash"),
        "verification_hash": package.get("verification_hash"),
        "verification_status": package.get("verification_status"),
        "verification_zip_sha256": package.get("verification_zip_sha256"),
        "verification_zip_size_bytes": package.get("verification_zip_size_bytes"),
        "verification_manifest_hash": package.get("verification_manifest_hash"),
        "signoff_hash": package.get("signoff_hash"),
        "signoff_status": package.get("signoff_status"),
    }


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return default if default is not None else {}
    try:
        value = read_json(path)
    except Exception:
        return default if default is not None else {}
    return sanitize_metadata(_as_document(value), blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)


def _write_json(path: Path, data: Any) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    rel = path.relative_to(root).as_posix()
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    rows = []
    for path in sorted(export_dir.rglob("*")):
        if path.is_file():
            rows.append((path, path.relative_to(export_dir).as_posix()))
    return rows


def _read_zip_json(zip_path: Path, name: str) -> ImplementationDocument:
    if not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            with archive.open(name, "r") as handle:
                value = json.loads(handle.read().decode("utf-8"))
    except Exception:
        return {}
    return sanitize_metadata(_as_document(value), blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ensure_within(root: Path, target: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if target_resolved != root_resolved and root_resolved not in target_resolved.parents:
        raise ReleasePortfolioGovernanceEvidenceVaultStateError("Resolved path escapes the Evidence Vault workspace.")


def _redaction_summary(value: Any) -> ImplementationDocument:
    text = json.dumps(sanitize_metadata(value, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS), ensure_ascii=False, sort_keys=True)
    findings: list[ImplementationDocument] = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": match.group(0)[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}


def _vault_markdown(report: ImplementationDocument, packages: list[ImplementationDocument]) -> str:
    summary = _as_document(report.get("summary"))
    lines = [
        "# MusicForge Portfolio Governance Evidence Vault",
        "",
        f"- Portfolio: {report.get('portfolio_id') or 'unknown'}",
        f"- Status: {report.get('status') or 'missing'}",
        f"- Required packages: {summary.get('required_package_count', 0)}",
        f"- Current packages: {summary.get('current_required_package_count', 0)}",
        "",
        "## Nested Packages",
    ]
    for item in packages:
        lines.append(f"- {item.get('package_id')}: {item.get('verification_status') or 'missing'} / current={bool(_package_verification_current(item))}")
    return "\n".join(lines) + "\n"


def _write_readme(export_dir: Path, report: ImplementationDocument) -> None:
    text = "\n".join(
        [
            "MusicForge Release Portfolio Governance Evidence Vault",
            "",
            "This package stores Final Board, Reviewer Pack, Governance Audit, Governance Archive, and Governance Queue evidence for offline review.",
            "Verify it with:",
            "python -m song_agent.cli verify-release-portfolio-governance-evidence-vault portfolio-governance-evidence-vault.zip --strict --deep --require-final-board --require-reviewer-pack --require-audit --require-archives",
            "",
            f"Portfolio: {report.get('portfolio_id') or 'unknown'}",
            f"Status: {report.get('status') or 'missing'}",
        ]
    )
    (export_dir / "README.txt").write_text(text + "\n", encoding="utf-8")


def _blocker(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "blocking", "message": sanitize_sensitive_text(message)}


def _warning(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "warning", "message": sanitize_sensitive_text(message)}


def _safe_queue_summary(queue: ImplementationDocument, governance_store: ReleasePortfolioGovernanceStore) -> ImplementationDocument:
    try:
        execution = governance_store.read_execution_report(str(queue.get("queue_id") or ""), default={})
    except Exception:
        execution = {}
    try:
        return queue_summary(queue, execution)
    except Exception:
        return {"queue_id": queue.get("queue_id"), "status": queue.get("status")}

_v142_rpgev_readiness.bind_globals(globals())
_v142_rpgev_evidence.bind_globals(globals())
