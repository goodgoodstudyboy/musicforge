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

ReleasePortfolioGovernanceEvidenceVaultNotFoundError = _make_deferred_global('ReleasePortfolioGovernanceEvidenceVaultNotFoundError')
ReleasePortfolioGovernanceEvidenceVaultStateError = _make_deferred_global('ReleasePortfolioGovernanceEvidenceVaultStateError')
_ensure_within = _make_deferred_global('_ensure_within')
_file_record = _make_deferred_global('_file_record')
_manifest_packages = _make_deferred_global('_manifest_packages')
_nested_manifest_integrity_ok = _make_deferred_global('_nested_manifest_integrity_ok')
_package_source_row = _make_deferred_global('_package_source_row')
_package_summaries = _make_deferred_global('_package_summaries')
_read_json_default = _make_deferred_global('_read_json_default')
_read_zip_json = _make_deferred_global('_read_zip_json')
_redaction_summary = _make_deferred_global('_redaction_summary')
_sha256 = _make_deferred_global('_sha256')
_summary_from_source = _make_deferred_global('_summary_from_source')
_vault_markdown = _make_deferred_global('_vault_markdown')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_zip_entries = _make_deferred_global('_zip_entries')
build_chain_of_custody = _make_deferred_global('build_chain_of_custody')
build_package_index = _make_deferred_global('build_package_index')
build_verification_index = _make_deferred_global('build_verification_index')
evidence_vault_summary = _make_deferred_global('evidence_vault_summary')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceEvidenceVaultNotFoundError, ReleasePortfolioGovernanceEvidenceVaultStateError, _ensure_within, _file_record, _manifest_packages, _nested_manifest_integrity_ok, _package_source_row
    global _package_summaries, _read_json_default, _read_zip_json, _redaction_summary, _sha256, _summary_from_source, _vault_markdown, _write_json
    global _write_readme, _zip_entries, build_chain_of_custody, build_package_index, build_verification_index, evidence_vault_summary, item
    ReleasePortfolioGovernanceEvidenceVaultNotFoundError = namespace.get('ReleasePortfolioGovernanceEvidenceVaultNotFoundError', ReleasePortfolioGovernanceEvidenceVaultNotFoundError)
    ReleasePortfolioGovernanceEvidenceVaultStateError = namespace.get('ReleasePortfolioGovernanceEvidenceVaultStateError', ReleasePortfolioGovernanceEvidenceVaultStateError)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _file_record = namespace.get('_file_record', _file_record)
    _manifest_packages = namespace.get('_manifest_packages', _manifest_packages)
    _nested_manifest_integrity_ok = namespace.get('_nested_manifest_integrity_ok', _nested_manifest_integrity_ok)
    _package_source_row = namespace.get('_package_source_row', _package_source_row)
    _package_summaries = namespace.get('_package_summaries', _package_summaries)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_zip_json = namespace.get('_read_zip_json', _read_zip_json)
    _redaction_summary = namespace.get('_redaction_summary', _redaction_summary)
    _sha256 = namespace.get('_sha256', _sha256)
    _summary_from_source = namespace.get('_summary_from_source', _summary_from_source)
    _vault_markdown = namespace.get('_vault_markdown', _vault_markdown)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    build_chain_of_custody = namespace.get('build_chain_of_custody', build_chain_of_custody)
    build_package_index = namespace.get('build_package_index', build_package_index)
    build_verification_index = namespace.get('build_verification_index', build_verification_index)
    evidence_vault_summary = namespace.get('evidence_vault_summary', evidence_vault_summary)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


EVIDENCE_VAULT_SCHEMA_VERSION = 1
EVIDENCE_VAULT_EXPORT_SCHEMA_VERSION = 1
SIGNED_STATUSES = {"signed", "force_signed"}




class ReleasePortfolioGovernanceEvidenceVaultStoreReadinessMixin:
    def root_dir(self, portfolio_id: str) -> Path:
        return self.portfolio_store.portfolio_dir(portfolio_id) / "governance-evidence-vault"

    def report_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "vault-report.json"

    def package_index_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "package-index.json"

    def verification_index_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "verification-index.json"

    def chain_of_custody_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "chain-of-custody.json"

    def history_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "vault-history.jsonl"

    def export_dir(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "export"

    def zip_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "portfolio-governance-evidence-vault.zip"

    def verification_report_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "verification-report.json"

    def read_report(self, portfolio_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.report_path(portfolio_id), default=default)

    def read_package_index(self, portfolio_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.package_index_path(portfolio_id), default=default)

    def read_verification_index(self, portfolio_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.verification_index_path(portfolio_id), default=default)

    def read_chain_of_custody(self, portfolio_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.chain_of_custody_path(portfolio_id), default=default)

    def read_export_manifest(self, portfolio_id: str) -> DomainDocument:
        path = self.export_dir(portfolio_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceEvidenceVaultNotFoundError("Portfolio Governance Evidence Vault export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(_as_document(value), blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)

    def refresh_report(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            self.portfolio_store.get_portfolio(portfolio_id)
            source, packages = self.build_source(portfolio_id, payload=payload)
            blockers, warnings, checks = self._findings(source, packages, payload)
            package_index = build_package_index(portfolio_id=portfolio_id, source_hash=stable_hash(source), packages=packages, generated_at=now)
            verification_index = build_verification_index(portfolio_id=portfolio_id, source_hash=stable_hash(source), packages=packages, generated_at=now)
            chain = build_chain_of_custody(portfolio_id=portfolio_id, source_hash=stable_hash(source), packages=packages, generated_at=now)
            summary = _summary_from_source(source, packages, blockers, warnings)
            report = {
                "schema_version": EVIDENCE_VAULT_SCHEMA_VERSION,
                "package_type": "release_portfolio_governance_evidence_vault_report",
                "report_id": self._reserve_report_id(portfolio_id),
                "portfolio_id": portfolio_id,
                "generated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "readiness": "blocked" if blockers else "vault_ready",
                "source_hash": stable_hash(source),
                "source": source,
                "summary": summary,
                "checks": checks,
                "nested_packages": _package_summaries(packages),
                "blockers": blockers,
                "warnings": warnings,
                "verification_instructions": {
                    "command": "python -m song_agent.cli verify-release-portfolio-governance-evidence-vault portfolio-governance-evidence-vault.zip --json --strict --deep --require-final-board --require-reviewer-pack --require-audit --require-archives",
                    "requires_deep": True,
                    "requires_final_board": True,
                    "requires_reviewer_pack": True,
                    "requires_audit": True,
                    "requires_archives": True,
                },
            }
            report["integrity_hash"] = evidence_vault_report_integrity_hash(report)
            report = sanitize_metadata(report, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)
            root = self.root_dir(portfolio_id)
            root.mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(portfolio_id), report)
            _write_json(self.package_index_path(portfolio_id), package_index)
            _write_json(self.verification_index_path(portfolio_id), verification_index)
            _write_json(self.chain_of_custody_path(portfolio_id), chain)
            self._append_history(portfolio_id, "report_refreshed", {"status": report["status"], "report_id": report["report_id"], "source_hash": report["source_hash"]}, now=now)
            return report

    def build_source(self, portfolio_id: str, payload: DomainDocument | None = None) -> tuple[DomainDocument, list[DomainDocument]]:
        payload = payload or {}
        portfolio = self.portfolio_store.get_portfolio(portfolio_id)
        portfolio_report = self.portfolio_store.read_report(portfolio_id, default={})
        final_report = self.final_board_store.read_report(portfolio_id, default={})
        final_signoff = self.final_board_store.read_signoff(portfolio_id, default={})
        final_summary = self.final_board_store.signoff_summary(portfolio_id, signoff=final_signoff) if final_signoff else final_board_signoff_summary(final_signoff)
        reviewer_report = self.reviewer_pack_store.read_report(portfolio_id, default={})
        audit_report = self.audit_store.read_report(portfolio_id, default={})
        queues = self.governance_store.list_queues(portfolio_id=portfolio_id, include_archived=True)
        packages: list[DomainDocument] = []
        packages.append(
            self._package_binding(
                package_id="final-board-archive",
                role="final_board_archive",
                package_type="release_portfolio_governance_final_board_archive",
                zip_path=self.final_board_store.archive_zip_path(portfolio_id),
                manifest_path=self.final_board_store.export_dir(portfolio_id) / "manifest.json",
                verification_path=self.final_board_store.verification_report_path(portfolio_id),
                vault_path="nested/final-board/portfolio-governance-final-board-archive.zip",
                verification_vault_path="nested/final-board/final-board-verification-report.json",
                required=bool(payload.get("require_final_board", True)),
            )
        )
        packages.append(
            self._package_binding(
                package_id="governance-reviewer-pack",
                role="governance_reviewer_pack",
                package_type="release_portfolio_governance_reviewer_pack",
                zip_path=self.reviewer_pack_store.zip_path(portfolio_id),
                manifest_path=self.reviewer_pack_store.export_dir(portfolio_id) / "manifest.json",
                verification_path=self.reviewer_pack_store.verification_report_path(portfolio_id),
                vault_path="nested/reviewer-pack/portfolio-governance-reviewer-pack.zip",
                verification_vault_path="nested/reviewer-pack/reviewer-pack-verification-report.json",
                required=bool(payload.get("require_reviewer_pack", True)),
            )
        )
        packages.append(
            self._package_binding(
                package_id="governance-audit",
                role="governance_audit",
                package_type="release_portfolio_governance_audit",
                zip_path=self.audit_store.zip_path(portfolio_id),
                manifest_path=self.audit_store.export_dir(portfolio_id) / "manifest.json",
                verification_path=self.audit_store.verification_report_path(portfolio_id),
                vault_path="nested/governance-audit/portfolio-governance-audit.zip",
                verification_vault_path="nested/governance-audit/audit-verification-report.json",
                required=bool(payload.get("require_audit", True)),
            )
        )
        require_archives = bool(payload.get("require_archives", True))
        require_queue_packages = bool(payload.get("require_queue_packages", False))
        signed_queue_ids: list[str] = []
        force_signed_queue_ids: list[str] = []
        for queue in sorted(queues, key=lambda item: str(item.get("created_at") or "")):
            queue_id = str(queue.get("queue_id") or "")
            if not queue_id:
                continue
            signoff = self.signoff_store.read_signoff(queue_id, default={})
            signoff_status = str(signoff.get("status") or "")
            if signoff_status not in SIGNED_STATUSES:
                continue
            signed_queue_ids.append(queue_id)
            if signoff_status == "force_signed":
                force_signed_queue_ids.append(queue_id)
            packages.append(
                self._package_binding(
                    package_id=f"governance-archive-{queue_id}",
                    role="governance_archive",
                    package_type="release_portfolio_governance_archive",
                    zip_path=self.signoff_store.archive_zip_path(queue_id),
                    manifest_path=self.signoff_store.archive_export_dir(queue_id) / "manifest.json",
                    verification_path=self.signoff_store.archive_verification_report_path(queue_id),
                    vault_path=f"nested/governance-archives/{queue_id}/governance-archive.zip",
                    verification_vault_path=f"nested/governance-archives/{queue_id}/governance-archive-verification-report.json",
                    required=require_archives,
                    queue_id=queue_id,
                    signoff_hash=signoff.get("integrity_hash") or governance_signoff_hash(signoff),
                    signoff_status=signoff_status,
                )
            )
            queue_required = require_queue_packages or bool(payload.get("include_queue_packages", True))
            packages.append(
                self._package_binding(
                    package_id=f"governance-queue-{queue_id}",
                    role="governance_queue",
                    package_type="release_portfolio_governance_queue",
                    zip_path=self.governance_store.zip_path(queue_id),
                    manifest_path=self.governance_store.export_dir(queue_id) / "manifest.json",
                    verification_path=self.governance_store.verification_report_path(queue_id),
                    vault_path=f"nested/governance-queues/{queue_id}/governance-queue.zip",
                    verification_vault_path=f"nested/governance-queues/{queue_id}/governance-queue-verification-report.json",
                    required=queue_required,
                    queue_id=queue_id,
                    signoff_hash=signoff.get("integrity_hash") or governance_signoff_hash(signoff),
                    signoff_status=signoff_status,
                )
            )
        source = {
            "portfolio_id": portfolio_id,
            "portfolio_hash": stable_hash(portfolio),
            "portfolio_report_hash": portfolio_report_integrity_hash(portfolio_report) if portfolio_report else None,
            "portfolio_report_integrity_hash": portfolio_report.get("integrity_hash") if portfolio_report else None,
            "portfolio_report_integrity_ok": portfolio_report_integrity_ok(portfolio_report) if portfolio_report else False,
            "portfolio_report_stale": self.portfolio_store.report_is_stale(portfolio_id, portfolio_report) if portfolio_report else False,
            "final_board_report_hash": final_board_report_integrity_hash(final_report) if final_report else None,
            "final_board_report_integrity_hash": final_report.get("integrity_hash") if final_report else None,
            "final_board_report_integrity_ok": final_board_report_integrity_ok(final_report) if final_report else False,
            "final_board_report_status": final_report.get("status") if final_report else "missing",
            "final_board_report_stale": self.final_board_store.report_is_stale(portfolio_id, final_report) if final_report else False,
            "final_board_signoff_hash": final_signoff.get("integrity_hash") or final_board_signoff_hash(final_signoff) if final_signoff else None,
            "final_board_signoff_integrity_ok": final_board_signoff_integrity_ok(final_signoff) if final_signoff else False,
            "final_board_signoff_status": final_summary.get("status"),
            "final_board_signoff_stale": final_summary.get("stale", False),
            "final_board_signoff_force": bool(final_signoff.get("force")),
            "reviewer_report_hash": reviewer_report_integrity_hash(reviewer_report) if reviewer_report else None,
            "reviewer_report_integrity_hash": reviewer_report.get("integrity_hash") if reviewer_report else None,
            "reviewer_report_integrity_ok": reviewer_report_integrity_ok(reviewer_report) if reviewer_report else False,
            "reviewer_report_status": reviewer_report.get("status") if reviewer_report else "missing",
            "reviewer_report_stale": self.reviewer_pack_store.report_is_stale(portfolio_id, reviewer_report) if reviewer_report else False,
            "governance_audit_report_hash": audit_report_integrity_hash(audit_report) if audit_report else None,
            "governance_audit_report_integrity_hash": audit_report.get("integrity_hash") if audit_report else None,
            "governance_audit_report_integrity_ok": audit_report_integrity_ok(audit_report) if audit_report else False,
            "governance_audit_report_status": audit_report.get("status") if audit_report else "missing",
            "governance_audit_report_stale": self.audit_store.report_is_stale(portfolio_id, audit_report) if audit_report else False,
            "queue_count": len(queues),
            "signed_queue_ids": signed_queue_ids,
            "signed_queue_count": len(signed_queue_ids),
            "force_signed_queue_ids": force_signed_queue_ids,
            "force_signed_queue_count": len(force_signed_queue_ids),
            "nested_package_hash": stable_hash([_package_source_row(item) for item in packages]),
        }
        return sanitize_metadata(source, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS), packages

    def report_is_stale(self, portfolio_id: str, report: DomainDocument | None = None) -> bool:
        data = _document_or(report, self.read_report(portfolio_id, default={}))
        if not data:
            return False
        try:
            source, _packages = self.build_source(portfolio_id)
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_vault(self, portfolio_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            report = self.read_report(portfolio_id, default={}) or self.refresh_report(portfolio_id, now=now)
            source, packages = self.build_source(portfolio_id)
            self._ensure_exportable(portfolio_id, report, source, packages)
            signoff_hash = str(source.get("final_board_signoff_hash") or "")
            if self._history_has_current_signoff_event(portfolio_id, signoff_hash, "vault_exported"):
                raise ReleasePortfolioGovernanceEvidenceVaultStateError("Evidence Vault export already exists for this Final Board signoff. Reset and re-sign Final Board before rebuilding vault evidence.")
            export_dir = self.export_dir(portfolio_id).resolve()
            root = self.root_dir(portfolio_id).resolve()
            _ensure_within(root, export_dir)
            existing_manifest = _read_json_default(export_dir / "manifest.json", default={})
            if existing_manifest.get("final_board_signoff", {}).get("integrity_hash") == signoff_hash:
                raise ReleasePortfolioGovernanceEvidenceVaultStateError("Evidence Vault export already exists for this Final Board signoff. Reset and re-sign Final Board before rebuilding vault evidence.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            package_index = build_package_index(portfolio_id=portfolio_id, source_hash=str(report.get("source_hash") or ""), packages=packages, generated_at=now)
            verification_index = build_verification_index(portfolio_id=portfolio_id, source_hash=str(report.get("source_hash") or ""), packages=packages, generated_at=now)
            chain = build_chain_of_custody(portfolio_id=portfolio_id, source_hash=str(report.get("source_hash") or ""), packages=packages, generated_at=now)
            _write_json(export_dir / "vault-report.json", report)
            _write_json(export_dir / "package-index.json", package_index)
            _write_json(export_dir / "verification-index.json", verification_index)
            _write_json(export_dir / "chain-of-custody.json", chain)
            (export_dir / "evidence-vault.md").write_text(_vault_markdown(report, packages), encoding="utf-8")
            _write_readme(export_dir, report)
            copied: list[DomainDocument] = []
            for package in packages:
                if not package.get("exists") and not package.get("verification_exists"):
                    continue
                if package.get("exists"):
                    target = export_dir / str(package.get("vault_path") or "")
                    _ensure_within(export_dir, target.resolve())
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(package["_source_path"], target)
                    copied.append({"package_id": package.get("package_id"), "path": package.get("vault_path"), "kind": "package"})
                if package.get("verification_exists"):
                    vtarget = export_dir / str(package.get("verification_vault_path") or "")
                    _ensure_within(export_dir, vtarget.resolve())
                    vtarget.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(package["_verification_source_path"], vtarget)
                    copied.append({"package_id": package.get("package_id"), "path": package.get("verification_vault_path"), "kind": "verification_report"})
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest = {
                "schema_version": EVIDENCE_VAULT_EXPORT_SCHEMA_VERSION,
                "package_type": EVIDENCE_VAULT_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Release Portfolio Governance Evidence Vault", "version": __version__},
                "portfolio_id": portfolio_id,
                "created_at": now,
                "app_version": __version__,
                "source_hash": report.get("source_hash"),
                "summary": report.get("summary", {}),
                "final_board_signoff": {"integrity_hash": signoff_hash, "status": source.get("final_board_signoff_status")},
                "vault_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "package_index": {"integrity_hash": package_index.get("integrity_hash"), "source_hash": package_index.get("source_hash")},
                "verification_index": {"integrity_hash": verification_index.get("integrity_hash"), "source_hash": verification_index.get("source_hash")},
                "chain_of_custody": {"integrity_hash": chain.get("integrity_hash"), "source_hash": chain.get("source_hash")},
                "nested_packages": _manifest_packages(packages),
                "copied": copied,
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"report": report, "package_index": package_index, "verification_index": verification_index, "chain": chain}),
            }
            manifest["integrity_hash"] = evidence_vault_manifest_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
            _write_json(self.package_index_path(portfolio_id), package_index)
            _write_json(self.verification_index_path(portfolio_id), verification_index)
            _write_json(self.chain_of_custody_path(portfolio_id), chain)
            self._append_history(portfolio_id, "vault_exported", {"file_count": len(files), "signoff_integrity_hash": signoff_hash, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)

    def build_zip(self, portfolio_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            source, packages = self.build_source(portfolio_id)
            report = self.read_report(portfolio_id, default={})
            self._ensure_exportable(portfolio_id, report, source, packages)
            signoff_hash = str(source.get("final_board_signoff_hash") or "")
            if self._history_has_current_signoff_event(portfolio_id, signoff_hash, "vault_zip_built"):
                raise ReleasePortfolioGovernanceEvidenceVaultStateError("Evidence Vault ZIP already exists for this Final Board signoff. Reset and re-sign Final Board before rebuilding vault evidence.")
            export_dir = self.export_dir(portfolio_id).resolve()
            root = self.root_dir(portfolio_id).resolve()
            zip_path = self.zip_path(portfolio_id).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "manifest.json").exists():
                self.export_vault(portfolio_id, now=now)
            if zip_path.exists():
                manifest_in_zip = _read_zip_json(zip_path, "manifest.json")
                if manifest_in_zip.get("final_board_signoff", {}).get("integrity_hash") == signoff_hash:
                    raise ReleasePortfolioGovernanceEvidenceVaultStateError("Evidence Vault ZIP already exists for this Final Board signoff. Reset and re-sign Final Board before rebuilding vault evidence.")
            manifest = read_json(export_dir / "manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = evidence_vault_manifest_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
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
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            self._append_history(portfolio_id, "vault_zip_built", {"sha256": info["sha256"], "entry_count": len(entries), "signoff_integrity_hash": signoff_hash}, now=now)
            return sanitize_metadata(info, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)

    def summary(self, portfolio_id: str) -> DomainDocument:
        report = self.read_report(portfolio_id, default={})
        verification = _read_json_default(self.verification_report_path(portfolio_id), default={})
        if not report:
            return {"status": "missing", "integrity_ok": False, "verification_status": verification.get("status") or "missing"}
        summary = evidence_vault_summary(report)
        summary["stale"] = self.report_is_stale(portfolio_id, report)
        summary["zip_sha256"] = _sha256(self.zip_path(portfolio_id)) if self.zip_path(portfolio_id).exists() else None
        summary["verification_status"] = verification.get("status") or "missing"
        summary["deep_verification_status"] = (_as_document(verification.get("summary"))).get("deep_verification_status") or "missing"
        return sanitize_metadata(summary, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)

    def _package_binding(
        self,
        *,
        package_id: str,
        role: str,
        package_type: str,
        zip_path: Path,
        manifest_path: Path,
        verification_path: Path,
        vault_path: str,
        verification_vault_path: str,
        required: bool,
        queue_id: str | None = None,
        signoff_hash: str | None = None,
        signoff_status: str | None = None,
    ) -> DomainDocument:
        zip_exists = zip_path.exists() and zip_path.is_file() and not zip_path.is_symlink()
        manifest = _read_json_default(manifest_path, default={})
        verification = _read_json_default(verification_path, default={})
        verification_exists = bool(verification_path.exists() and verification_path.is_file() and not verification_path.is_symlink())
        return {
                "package_id": package_id,
                "role": role,
                "package_type": package_type,
                "queue_id": queue_id,
                "signoff_hash": signoff_hash,
                "signoff_status": signoff_status,
                "required": bool(required),
                "exists": zip_exists,
                "_source_path": zip_path,
                "vault_path": vault_path,
                "sha256": _sha256(zip_path) if zip_exists else None,
                "size_bytes": zip_path.stat().st_size if zip_exists else None,
                "manifest_exists": bool(manifest),
                "manifest_hash": manifest.get("integrity_hash") if manifest else None,
                "manifest_package_type": manifest.get("package_type") if manifest else None,
                "manifest_integrity_ok": _nested_manifest_integrity_ok(package_type, manifest) if manifest else False,
                "verification_exists": verification_exists,
                "_verification_source_path": verification_path,
                "verification_vault_path": verification_vault_path,
                "verification_hash": stable_hash(verification) if verification else None,
                "verification_status": verification.get("status") if verification else "missing",
                "verification_zip_sha256": verification.get("zip_sha256") if verification else None,
                "verification_zip_size_bytes": verification.get("zip_size_bytes") if verification else None,
                "verification_manifest_hash": verification.get("manifest_hash") if verification else None,
            }
