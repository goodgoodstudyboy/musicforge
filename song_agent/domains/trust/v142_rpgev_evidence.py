# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
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
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore as ReleasePortfolioAuditStore, portfolio_report_integrity_hash as portfolio_report_integrity_hash, portfolio_report_integrity_ok as portfolio_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance import ReleasePortfolioGovernanceStore as ReleasePortfolioGovernanceStore, queue_integrity_ok as queue_integrity_ok, queue_summary as queue_summary
from song_agent.domains.trust.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore as ReleasePortfolioGovernanceAuditStore, audit_report_integrity_hash as audit_report_integrity_hash, audit_report_integrity_ok as audit_report_integrity_ok, audit_summary as audit_summary
from song_agent.domains.trust.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore as ReleasePortfolioGovernanceFinalBoardStore, final_board_archive_manifest_integrity_ok as final_board_archive_manifest_integrity_ok, final_board_report_integrity_hash as final_board_report_integrity_hash, final_board_report_integrity_ok as final_board_report_integrity_ok, final_board_signoff_hash as final_board_signoff_hash, final_board_signoff_integrity_ok as final_board_signoff_integrity_ok, final_board_signoff_summary as final_board_signoff_summary, final_board_summary as final_board_summary
from song_agent.domains.trust.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore as ReleasePortfolioGovernanceReviewerPackStore, reviewer_pack_manifest_integrity_ok as reviewer_pack_manifest_integrity_ok, reviewer_pack_summary as reviewer_pack_summary, reviewer_report_integrity_hash as reviewer_report_integrity_hash, reviewer_report_integrity_ok as reviewer_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore as ReleasePortfolioGovernanceSignoffStore, governance_archive_manifest_integrity_ok as governance_archive_manifest_integrity_ok, governance_signoff_hash as governance_signoff_hash, governance_signoff_integrity_ok as governance_signoff_integrity_ok, governance_signoff_summary as governance_signoff_summary
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_evidence_vault_contracts import EVIDENCE_VAULT_BLOCKED_KEYS as EVIDENCE_VAULT_BLOCKED_KEYS, EVIDENCE_VAULT_INDEX_HASH_EXCLUDE_KEYS as EVIDENCE_VAULT_INDEX_HASH_EXCLUDE_KEYS, EVIDENCE_VAULT_MANIFEST_HASH_EXCLUDE_KEYS as EVIDENCE_VAULT_MANIFEST_HASH_EXCLUDE_KEYS, EVIDENCE_VAULT_PACKAGE_TYPE as EVIDENCE_VAULT_PACKAGE_TYPE, EVIDENCE_VAULT_REPORT_HASH_EXCLUDE_KEYS as EVIDENCE_VAULT_REPORT_HASH_EXCLUDE_KEYS, evidence_vault_chain_hash as evidence_vault_chain_hash, evidence_vault_manifest_hash as evidence_vault_manifest_hash, evidence_vault_package_index_hash as evidence_vault_package_index_hash, evidence_vault_report_integrity_hash as evidence_vault_report_integrity_hash, evidence_vault_verification_index_hash as evidence_vault_verification_index_hash, evidence_vault_verification_summary as evidence_vault_verification_summary

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

ReleasePortfolioGovernanceEvidenceVaultStateError = _make_deferred_global('ReleasePortfolioGovernanceEvidenceVaultStateError')
_blocker = _make_deferred_global('_blocker')
_package_summaries = _make_deferred_global('_package_summaries')
_package_verification_current = _make_deferred_global('_package_verification_current')
_redaction_summary = _make_deferred_global('_redaction_summary')
_warning = _make_deferred_global('_warning')
evidence_vault_report_integrity_ok = _make_deferred_global('evidence_vault_report_integrity_ok')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceEvidenceVaultStateError, _blocker, _package_summaries, _package_verification_current, _redaction_summary, _warning, evidence_vault_report_integrity_ok
    ReleasePortfolioGovernanceEvidenceVaultStateError = namespace.get('ReleasePortfolioGovernanceEvidenceVaultStateError', ReleasePortfolioGovernanceEvidenceVaultStateError)
    _blocker = namespace.get('_blocker', _blocker)
    _package_summaries = namespace.get('_package_summaries', _package_summaries)
    _package_verification_current = namespace.get('_package_verification_current', _package_verification_current)
    _redaction_summary = namespace.get('_redaction_summary', _redaction_summary)
    _warning = namespace.get('_warning', _warning)
    evidence_vault_report_integrity_ok = namespace.get('evidence_vault_report_integrity_ok', evidence_vault_report_integrity_ok)
    _bind_deferred_defaults(namespace)


EVIDENCE_VAULT_SCHEMA_VERSION = 1
EVIDENCE_VAULT_EXPORT_SCHEMA_VERSION = 1
SIGNED_STATUSES = {"signed", "force_signed"}




class ReleasePortfolioGovernanceEvidenceVaultStoreEvidenceMixin:
    def _findings(self, source: DomainDocument, packages: list[DomainDocument], payload: DomainDocument) -> tuple[list[DomainDocument], list[DomainDocument], list[DomainDocument]]:
        blockers: list[DomainDocument] = []
        warnings: list[DomainDocument] = []
        checks: list[DomainDocument] = []

        def check(check_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            status = "passed" if passed else "warning" if warning else "failed"
            item = {"check_id": check_id, "status": status, "severity": "warning" if warning else "blocking", "message": message}
            checks.append(item)
            if passed:
                return
            if warning:
                warnings.append(_warning(check_id, message))
            else:
                blockers.append(_blocker(check_id, message))

        check("portfolio_report_current", bool(source.get("portfolio_report_integrity_ok")) and not source.get("portfolio_report_stale"), "Portfolio Audit report is current.")
        check("final_board_report_current", bool(source.get("final_board_report_integrity_ok")) and not source.get("final_board_report_stale") and source.get("final_board_report_status") != "failed", "Final Board Report is current.")
        check("final_board_signoff_current", source.get("final_board_signoff_status") in SIGNED_STATUSES and bool(source.get("final_board_signoff_integrity_ok")) and not source.get("final_board_signoff_stale"), "Final Board Signoff is signed, current, and integrity-valid.")
        check("reviewer_pack_report_current", bool(source.get("reviewer_report_integrity_ok")) and not source.get("reviewer_report_stale") and source.get("reviewer_report_status") != "failed", "Governance Reviewer Pack report is current.")
        check("governance_audit_report_current", bool(source.get("governance_audit_report_integrity_ok")) and not source.get("governance_audit_report_stale") and source.get("governance_audit_report_status") != "failed", "Governance Audit report is current.")
        if bool(source.get("final_board_signoff_force")):
            check("final_board_force_signoff", False, "Final Board was force signed.", warning=not bool(payload.get("require_no_force", False)))
        signed_queue_count = int(source.get("signed_queue_count") or 0)
        check("signed_queue_coverage", signed_queue_count > 0, "At least one signed Governance Queue is covered.")

        package_labels = {
            "final_board_archive": "Final Board Archive",
            "governance_reviewer_pack": "Reviewer Pack",
            "governance_audit": "Governance Audit",
            "governance_archive": "Governance Archive",
            "governance_queue": "Governance Queue",
        }
        for package in packages:
            if not package.get("required"):
                continue
            package_id = str(package.get("package_id") or "package")
            label = package_labels.get(str(package.get("role") or ""), package_id)
            check(f"{package_id}_zip_exists", bool(package.get("exists")), f"{label} ZIP exists.")
            check(f"{package_id}_manifest_exists", bool(package.get("manifest_exists")), f"{label} export manifest exists.")
            check(f"{package_id}_manifest_integrity", bool(package.get("manifest_integrity_ok")), f"{label} export manifest integrity is valid.")
            check(
                f"{package_id}_verification_current",
                _package_verification_current(package),
                f"{label} verification report matches the current ZIP and manifest.",
            )
        if _redaction_summary({"source": source, "packages": _package_summaries(packages)}).get("status") == "failed":
            check("redaction_scan", False, "Evidence Vault source contains sensitive values.")
        else:
            check("redaction_scan", True, "No sensitive values found in Evidence Vault source.")
        return blockers, warnings, checks

    def _ensure_exportable(self, portfolio_id: str, report: DomainDocument, source: DomainDocument, packages: list[DomainDocument]) -> None:
        if not report:
            raise ReleasePortfolioGovernanceEvidenceVaultStateError("Evidence Vault Report does not exist. Refresh before export.")
        if not evidence_vault_report_integrity_ok(report):
            raise ReleasePortfolioGovernanceEvidenceVaultStateError("Evidence Vault Report integrity failed. Refresh before export.")
        if self.report_is_stale(portfolio_id, report):
            raise ReleasePortfolioGovernanceEvidenceVaultStateError("Evidence Vault source is stale. Refresh before export.")
        if str(report.get("source_hash") or "") != stable_hash(source):
            raise ReleasePortfolioGovernanceEvidenceVaultStateError("Evidence Vault source is stale. Refresh before export.")
        blockers, _warnings, _checks = self._findings(source, packages, {})
        if blockers or report.get("status") == "failed":
            detail = str((blockers[0] if blockers else {}).get("message") or "Evidence Vault Report is failed.")
            raise ReleasePortfolioGovernanceEvidenceVaultStateError(f"Evidence Vault cannot be exported: {detail}")

    def _history_has_current_signoff_event(self, portfolio_id: str, signoff_hash: str, event_type: str) -> bool:
        if not signoff_hash:
            return False
        path = self.history_path(portfolio_id)
        if not path.exists():
            return False
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or str(event.get("type") or "") != event_type:
                continue
            summary = _as_document(event.get("summary"))
            if str(summary.get("signoff_integrity_hash") or "") == signoff_hash:
                return True
        return False

    def _reserve_report_id(self, portfolio_id: str) -> str:
        existing = self.read_report(portfolio_id, default={})
        if str(existing.get("report_id") or "").startswith("gev-"):
            return str(existing.get("report_id"))
        return "gev-000001"

    def _append_history(self, portfolio_id: str, event_type: str, summary: DomainDocument, *, now: str | None = None) -> None:
        path = self.history_path(portfolio_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"geve-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
