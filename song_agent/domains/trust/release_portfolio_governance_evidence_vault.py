from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, document_or as _document_or
from song_agent.platform.contracts.packages import require_registered_package_type as _require_registered_package_type

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


EVIDENCE_VAULT_SCHEMA_VERSION = 1
EVIDENCE_VAULT_EXPORT_SCHEMA_VERSION = 1





SIGNED_STATUSES = {"signed", "force_signed"}


class ReleasePortfolioGovernanceEvidenceVaultError(ValueError):
    pass


class ReleasePortfolioGovernanceEvidenceVaultNotFoundError(ReleasePortfolioGovernanceEvidenceVaultError):
    pass


class ReleasePortfolioGovernanceEvidenceVaultStateError(ReleasePortfolioGovernanceEvidenceVaultError):
    pass


class ReleasePortfolioGovernanceEvidenceVaultStore:
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

    def read_report(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(portfolio_id), default=default)

    def read_package_index(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.package_index_path(portfolio_id), default=default)

    def read_verification_index(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.verification_index_path(portfolio_id), default=default)

    def read_chain_of_custody(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.chain_of_custody_path(portfolio_id), default=default)

    def read_export_manifest(self, portfolio_id: str) -> dict[str, Any]:
        path = self.export_dir(portfolio_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceEvidenceVaultNotFoundError("Portfolio Governance Evidence Vault export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(_as_document(value), blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)

    def refresh_report(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def build_source(self, portfolio_id: str, payload: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        payload = payload or {}
        portfolio = self.portfolio_store.get_portfolio(portfolio_id)
        portfolio_report = self.portfolio_store.read_report(portfolio_id, default={})
        final_report = self.final_board_store.read_report(portfolio_id, default={})
        final_signoff = self.final_board_store.read_signoff(portfolio_id, default={})
        final_summary = self.final_board_store.signoff_summary(portfolio_id, signoff=final_signoff) if final_signoff else final_board_signoff_summary(final_signoff)
        reviewer_report = self.reviewer_pack_store.read_report(portfolio_id, default={})
        audit_report = self.audit_store.read_report(portfolio_id, default={})
        queues = self.governance_store.list_queues(portfolio_id=portfolio_id, include_archived=True)
        packages: list[dict[str, Any]] = []
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

    def report_is_stale(self, portfolio_id: str, report: dict[str, Any] | None = None) -> bool:
        data = _document_or(report, self.read_report(portfolio_id, default={}))
        if not data:
            return False
        try:
            source, _packages = self.build_source(portfolio_id)
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_vault(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
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
            copied: list[dict[str, Any]] = []
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

    def build_zip(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
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

    def summary(self, portfolio_id: str) -> dict[str, Any]:
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
    ) -> ImplementationDocument:
        zip_exists = zip_path.exists() and zip_path.is_file() and not zip_path.is_symlink()
        manifest = _read_json_default(manifest_path, default={})
        verification = _read_json_default(verification_path, default={})
        verification_exists = bool(verification_path.exists() and verification_path.is_file() and not verification_path.is_symlink())
        return {
                "package_id": package_id,
                "role": role,
                "package_type": _require_registered_package_type(package_type, writer_id="song_agent.domains.trust.release_portfolio_governance_evidence_vault.ReleasePortfolioGovernanceEvidenceVaultStore._package_binding"),
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

    def _findings(self, source: ImplementationDocument, packages: list[ImplementationDocument], payload: ImplementationDocument) -> tuple[list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []

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

    def _ensure_exportable(self, portfolio_id: str, report: ImplementationDocument, source: ImplementationDocument, packages: list[ImplementationDocument]) -> None:
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

    def _append_history(self, portfolio_id: str, event_type: str, summary: ImplementationDocument, *, now: str | None = None) -> None:
        path = self.history_path(portfolio_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"geve-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def build_package_index(*, portfolio_id: str, source_hash: str, packages: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
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


def build_verification_index(*, portfolio_id: str, source_hash: str, packages: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
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


def build_chain_of_custody(*, portfolio_id: str, source_hash: str, packages: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
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




def evidence_vault_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_vault_report_integrity_hash(data)





def evidence_vault_package_index_integrity_ok(index: dict[str, Any] | None) -> bool:
    data = _as_document(index)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_vault_package_index_hash(data)





def evidence_vault_verification_index_integrity_ok(index: dict[str, Any] | None) -> bool:
    data = _as_document(index)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_vault_verification_index_hash(data)





def evidence_vault_chain_integrity_ok(chain: dict[str, Any] | None) -> bool:
    data = _as_document(chain)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_vault_chain_hash(data)





def evidence_vault_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_vault_manifest_hash(data)


def evidence_vault_summary(report: dict[str, Any] | None) -> dict[str, Any]:
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
    findings: list[dict[str, Any]] = []
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
