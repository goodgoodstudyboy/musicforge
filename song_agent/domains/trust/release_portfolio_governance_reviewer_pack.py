from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.projects import now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_audit import portfolio_report_integrity_hash, portfolio_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore, audit_ledger_hash, audit_ledger_integrity_ok, audit_report_integrity_hash, audit_report_integrity_ok, audit_summary
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.release_portfolio_governance_reviewer_pack_contracts import EVIDENCE_INDEX_HASH_EXCLUDE_KEYS, PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS, RETROSPECTIVE_REPORT_HASH_EXCLUDE_KEYS, REVIEWER_PACK_MANIFEST_HASH_EXCLUDE_KEYS, REVIEWER_REPORT_HASH_EXCLUDE_KEYS, TIMELINE_HASH_EXCLUDE_KEYS, evidence_index_integrity_hash, retrospective_report_integrity_hash, reviewer_pack_manifest_integrity_hash, reviewer_report_integrity_hash, timeline_integrity_hash


PORTFOLIO_GOVERNANCE_REVIEWER_PACK_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_REVIEWER_PACK_EXPORT_SCHEMA_VERSION = 1








class ReleasePortfolioGovernanceReviewerPackError(ValueError):
    pass


class ReleasePortfolioGovernanceReviewerPackNotFoundError(ReleasePortfolioGovernanceReviewerPackError):
    pass


class ReleasePortfolioGovernanceReviewerPackStateError(ReleasePortfolioGovernanceReviewerPackError):
    pass


class ReleasePortfolioGovernanceReviewerPackStore:
    def __init__(self, *, audit_store: ReleasePortfolioGovernanceAuditStore) -> None:
        self.audit_store = audit_store
        self.portfolio_store = audit_store.portfolio_store
        self.lock = threading.RLock()

    def root_dir(self, portfolio_id: str) -> Path:
        return self.portfolio_store.portfolio_dir(portfolio_id) / "governance-reviewer-pack"

    def report_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "reviewer-report.json"

    def retrospective_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "retrospective-report.json"

    def evidence_index_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "evidence-index.json"

    def timeline_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "timeline.json"

    def export_dir(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "export"

    def zip_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "portfolio-governance-reviewer-pack.zip"

    def verification_report_path(self, portfolio_id: str) -> Path:
        return self.root_dir(portfolio_id) / "portfolio-governance-reviewer-pack-verification-report.json"

    def read_report(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_or_default(self.report_path(portfolio_id), default)

    def read_retrospective(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_or_default(self.retrospective_path(portfolio_id), default)

    def read_evidence_index(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_or_default(self.evidence_index_path(portfolio_id), default)

    def read_timeline(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_or_default(self.timeline_path(portfolio_id), default)

    def read_export_manifest(self, portfolio_id: str) -> dict[str, Any]:
        path = self.export_dir(portfolio_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceReviewerPackNotFoundError("Portfolio Governance Reviewer Pack export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)

    def report_is_stale(self, portfolio_id: str, report: dict[str, Any] | None = None) -> bool:
        data = report if isinstance(report, dict) else self.read_report(portfolio_id, default={})
        if not data:
            return False
        try:
            source = self.build_source(portfolio_id)
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def refresh(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            now = now or now_iso()
            self.portfolio_store.get_portfolio(portfolio_id)
            source = self.build_source(portfolio_id)
            audit_report = self.audit_store.read_report(portfolio_id, default={})
            ledger_entries = self.audit_store.read_ledger(portfolio_id)
            audit_verification = _read_optional_json(self.audit_store.verification_report_path(portfolio_id))
            audit_export_manifest = _read_optional_json(self.audit_store.export_dir(portfolio_id) / "manifest.json")
            evidence_index = build_evidence_index(
                portfolio_id=portfolio_id,
                source_hash=stable_hash(source),
                audit_report=audit_report,
                ledger_entries=ledger_entries,
                audit_verification=audit_verification,
                audit_export_manifest=audit_export_manifest,
                generated_at=now,
            )
            timeline = build_timeline(portfolio_id=portfolio_id, source_hash=stable_hash(source), ledger_entries=ledger_entries, generated_at=now)
            blockers, warnings = self._reviewer_findings(portfolio_id, audit_report, ledger_entries, audit_verification)
            retrospective = build_retrospective_report(
                portfolio_id=portfolio_id,
                source_hash=stable_hash(source),
                audit_report=audit_report,
                ledger_entries=ledger_entries,
                timeline=timeline,
                warnings=warnings,
                blockers=blockers,
                generated_at=now,
            )
            coverage = audit_report.get("coverage") if isinstance(audit_report.get("coverage"), dict) else {}
            audit_report_summary = audit_report.get("summary") if isinstance(audit_report.get("summary"), dict) else {}
            portfolio = self.portfolio_store.get_portfolio(portfolio_id)
            summary = {
                "portfolio_name": portfolio.get("name"),
                "audit_status": audit_report.get("status") or "missing",
                "audit_package_verification_status": audit_verification.get("status") or "missing",
                "audit_ledger_hash": audit_report.get("ledger_hash"),
                "queue_count": int(coverage.get("queue_count") or audit_report_summary.get("queue_count") or 0),
                "signed_queue_count": int(coverage.get("signed_queue_count") or audit_report_summary.get("signed_queue_count") or 0),
                "force_signed_queue_count": int(coverage.get("force_signed_count") or 0),
                "reset_count": int(coverage.get("reset_count") or 0),
                "archive_verified_count": int(coverage.get("archive_verified_count") or audit_report_summary.get("archive_verified_count") or 0),
                "applied_change_request_count": int(coverage.get("applied_change_request_count") or 0),
                "reset_causality_status": _reset_causality_status(ledger_entries),
                "evidence_count": len(evidence_index.get("items", []) if isinstance(evidence_index.get("items"), list) else []),
                "timeline_event_count": len(timeline.get("events", []) if isinstance(timeline.get("events"), list) else []),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
            }
            report = {
                "schema_version": PORTFOLIO_GOVERNANCE_REVIEWER_PACK_SCHEMA_VERSION,
                "package_type": "release_portfolio_governance_reviewer_report",
                "portfolio_id": portfolio_id,
                "generated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "readiness": "blocked" if blockers else "reviewable",
                "source_hash": stable_hash(source),
                "source": source,
                "summary": summary,
                "reviewer_findings": warnings,
                "risk_summary": _risk_summary(audit_report, ledger_entries, blockers, warnings),
                "change_control": audit_report.get("change_request_summary", {}),
                "verification_instructions": {
                    "command": "python -m song_agent.cli verify-release-portfolio-governance-reviewer-pack portfolio-governance-reviewer-pack.zip --json --strict --require-audit --require-signed --require-archives",
                    "requires_audit": True,
                    "requires_signed": True,
                    "requires_archives": True,
                },
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = reviewer_report_integrity_hash(report)
            report = sanitize_metadata(report, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)
            root = self.root_dir(portfolio_id)
            root.mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(portfolio_id), report)
            _write_json(self.retrospective_path(portfolio_id), retrospective)
            _write_json(self.evidence_index_path(portfolio_id), evidence_index)
            _write_json(self.timeline_path(portfolio_id), timeline)
            return report

    def build_source(self, portfolio_id: str) -> dict[str, Any]:
        portfolio = self.portfolio_store.get_portfolio(portfolio_id)
        portfolio_report = self.portfolio_store.read_report(portfolio_id, default={})
        audit_report = self.audit_store.read_report(portfolio_id, default={})
        ledger_entries = self.audit_store.read_ledger(portfolio_id)
        audit_export_manifest = _read_optional_json(self.audit_store.export_dir(portfolio_id) / "manifest.json")
        audit_verification = _read_optional_json(self.audit_store.verification_report_path(portfolio_id))
        audit_binding = self._current_audit_package_binding(portfolio_id)
        return sanitize_metadata(
            {
                "portfolio_id": portfolio_id,
                "portfolio_hash": stable_hash(portfolio),
                "portfolio_report_hash": portfolio_report_integrity_hash(portfolio_report) if portfolio_report else None,
                "portfolio_report_integrity_hash": portfolio_report.get("integrity_hash") if portfolio_report else None,
                "portfolio_report_integrity_ok": portfolio_report_integrity_ok(portfolio_report) if portfolio_report else False,
                "governance_audit_report_hash": audit_report_integrity_hash(audit_report) if audit_report else None,
                "governance_audit_report_integrity_hash": audit_report.get("integrity_hash") if audit_report else None,
                "governance_audit_report_source_hash": audit_report.get("source_hash") if audit_report else None,
                "governance_audit_report_stale": self.audit_store.report_is_stale(portfolio_id, audit_report) if audit_report else False,
                "governance_audit_ledger_hash": audit_ledger_hash(ledger_entries) if ledger_entries else None,
                "governance_audit_report_ledger_hash": audit_report.get("ledger_hash") if audit_report else None,
                "governance_audit_export_manifest_hash": audit_export_manifest.get("integrity_hash") if audit_export_manifest else None,
                "governance_audit_zip_sha256": audit_binding.get("zip_sha256"),
                "governance_audit_zip_size_bytes": audit_binding.get("zip_size_bytes"),
                "governance_audit_verification_status": audit_verification.get("status") if audit_verification else None,
                "governance_audit_verification_zip_sha256": audit_verification.get("zip_sha256") if audit_verification else None,
                "governance_audit_verification_zip_size_bytes": audit_verification.get("zip_size_bytes") if audit_verification else None,
                "governance_audit_verification_manifest_hash": audit_verification.get("manifest_hash") if audit_verification else None,
                "governance_audit_verification_hash": stable_hash(audit_verification) if audit_verification else None,
                "queue_summaries_hash": stable_hash(audit_report.get("queue_summaries", [])) if audit_report else None,
                "change_request_summary_hash": stable_hash(audit_report.get("change_request_summary", {})) if audit_report else None,
                "archive_summary_hash": stable_hash(audit_report.get("archive_summary", {})) if audit_report else None,
            },
            blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS,
        )

    def export_pack(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            report = self.read_report(portfolio_id, default={}) or self.refresh(portfolio_id, now=now)
            if self.report_is_stale(portfolio_id, report):
                raise ReleasePortfolioGovernanceReviewerPackStateError("Portfolio Governance Reviewer Pack source is stale. Refresh before export.")
            retrospective = self.read_retrospective(portfolio_id, default={})
            evidence_index = self.read_evidence_index(portfolio_id, default={})
            timeline = self.read_timeline(portfolio_id, default={})
            if not reviewer_report_integrity_ok(report):
                raise ReleasePortfolioGovernanceReviewerPackStateError("Portfolio Governance Reviewer Report integrity failed. Refresh before export.")
            if not retrospective_report_integrity_ok(retrospective):
                raise ReleasePortfolioGovernanceReviewerPackStateError("Portfolio Governance Retrospective integrity failed. Refresh before export.")
            if not evidence_index_integrity_ok(evidence_index):
                raise ReleasePortfolioGovernanceReviewerPackStateError("Portfolio Governance Evidence Index integrity failed. Refresh before export.")
            if not timeline_integrity_ok(timeline):
                raise ReleasePortfolioGovernanceReviewerPackStateError("Portfolio Governance Timeline integrity failed. Refresh before export.")
            export_dir = self.export_dir(portfolio_id).resolve()
            portfolio_dir = self.portfolio_store.portfolio_dir(portfolio_id).resolve()
            _ensure_within(portfolio_dir, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            audit_report = self.audit_store.read_report(portfolio_id, default={})
            audit_verification = _read_optional_json(self.audit_store.verification_report_path(portfolio_id))
            ledger_entries = self.audit_store.read_ledger(portfolio_id)
            _write_json(export_dir / "reviewer-report.json", report)
            _write_json(export_dir / "retrospective-report.json", retrospective)
            _write_json(export_dir / "evidence-index.json", evidence_index)
            _write_json(export_dir / "timeline.json", timeline)
            _write_json(export_dir / "audit-summary.json", {"summary": audit_summary(audit_report), "verification": _verification_summary(audit_verification)})
            _write_json(export_dir / "queue-summaries.json", {"items": audit_report.get("queue_summaries", []), "count": len(audit_report.get("queue_summaries", []) if isinstance(audit_report.get("queue_summaries"), list) else [])})
            _write_json(export_dir / "signoff-summaries.json", {"items": [item for item in audit_report.get("queue_summaries", []) if isinstance(item, dict) and item.get("signoff_status")], "count": (audit_report.get("coverage") if isinstance(audit_report.get("coverage"), dict) else {}).get("signed_queue_count", 0)})
            _write_json(export_dir / "archive-verification-summaries.json", audit_report.get("archive_summary", {}))
            _write_json(export_dir / "change-request-ledger.json", audit_report.get("change_request_summary", {}))
            _write_json(export_dir / "risk-summary.json", report.get("risk_summary", {}))
            (export_dir / "REVIEWER_GUIDE.md").write_text(_reviewer_guide(report), encoding="utf-8")
            (export_dir / "RETROSPECTIVE.md").write_text(_retrospective_markdown(retrospective), encoding="utf-8")
            (export_dir / "evidence-index.md").write_text(_evidence_index_markdown(evidence_index), encoding="utf-8")
            (export_dir / "timeline.md").write_text(_timeline_markdown(timeline), encoding="utf-8")
            (export_dir / "report.md").write_text(_report_markdown(report), encoding="utf-8")
            _write_readme(export_dir, report)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest = {
                "schema_version": PORTFOLIO_GOVERNANCE_REVIEWER_PACK_EXPORT_SCHEMA_VERSION,
                "package_type": "release_portfolio_governance_reviewer_pack",
                "tool": {"name": "MusicForge Release Portfolio Governance Reviewer Pack", "version": __version__},
                "portfolio_id": portfolio_id,
                "generated_at": now,
                "app_version": __version__,
                "source_hash": report.get("source_hash"),
                "summary": {"status": report.get("status"), **(report.get("summary") if isinstance(report.get("summary"), dict) else {})},
                "reviewer_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "retrospective_report": {"integrity_hash": retrospective.get("integrity_hash"), "source_hash": retrospective.get("source_hash")},
                "evidence_index": {"integrity_hash": evidence_index.get("integrity_hash"), "source_hash": evidence_index.get("source_hash")},
                "timeline": {"integrity_hash": timeline.get("integrity_hash"), "source_hash": timeline.get("source_hash")},
                "audit_summary": {
                    "status": audit_report.get("status") or "missing",
                    "ledger_hash": audit_report.get("ledger_hash"),
                    "integrity_hash": audit_report.get("integrity_hash"),
                    "audit_package_verification_status": audit_verification.get("status") or "missing",
                    "audit_package_verification_hash": stable_hash(audit_verification) if audit_verification else None,
                },
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"report": report, "retrospective": retrospective, "evidence_index": evidence_index, "timeline": timeline, "ledger": ledger_entries}),
            }
            manifest["integrity_hash"] = reviewer_pack_manifest_integrity_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
            return sanitize_metadata(manifest, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)

    def build_zip(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            export_dir = self.export_dir(portfolio_id).resolve()
            portfolio_dir = self.portfolio_store.portfolio_dir(portfolio_id).resolve()
            zip_path = self.zip_path(portfolio_id).resolve()
            _ensure_within(portfolio_dir, export_dir)
            _ensure_within(portfolio_dir, zip_path)
            if not (export_dir / "manifest.json").exists():
                self.export_pack(portfolio_id, now=now)
            report = self.read_report(portfolio_id, default={})
            if self.report_is_stale(portfolio_id, report):
                raise ReleasePortfolioGovernanceReviewerPackStateError("Portfolio Governance Reviewer Pack source is stale. Refresh before ZIP export.")
            manifest = read_json(export_dir / "manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = reviewer_pack_manifest_integrity_hash(manifest)
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
            return sanitize_metadata({"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)

    def summary(self, portfolio_id: str) -> dict[str, Any]:
        return reviewer_pack_summary(self.read_report(portfolio_id, default={}))

    def _reviewer_findings(self, portfolio_id: str, audit_report: dict[str, Any], ledger_entries: list[dict[str, Any]], audit_verification: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        if not audit_report:
            blockers.append(_blocker("governance_audit_missing", "Portfolio Governance Audit Report is missing."))
        elif not audit_report_integrity_ok(audit_report):
            blockers.append(_blocker("governance_audit_integrity", "Portfolio Governance Audit Report integrity failed."))
        elif self.audit_store.report_is_stale(portfolio_id, audit_report):
            blockers.append(_blocker("governance_audit_stale", "Portfolio Governance Audit Report is stale. Refresh Governance Audit before building reviewer pack."))
        elif audit_report.get("status") == "failed":
            blockers.append(_blocker("governance_audit_failed", "Portfolio Governance Audit Report is failed."))
        elif audit_report.get("status") == "warning":
            warnings.append(_warning("governance_audit_warning", "Portfolio Governance Audit Report has warnings."))
        if not ledger_entries:
            blockers.append(_blocker("governance_audit_ledger_missing", "Portfolio Governance Audit Ledger is missing."))
        elif not audit_ledger_integrity_ok(ledger_entries):
            blockers.append(_blocker("governance_audit_ledger_chain", "Portfolio Governance Audit Ledger hash chain failed."))
        if not audit_verification:
            blockers.append(_blocker("governance_audit_verification_missing", "Portfolio Governance Audit package verification report is missing."))
        elif audit_verification.get("status") != "passed":
            blockers.append(_blocker("governance_audit_verification_failed", "Portfolio Governance Audit package verification failed."))
        else:
            audit_binding = self._current_audit_package_binding(portfolio_id)
            verification_zip_sha256 = str(audit_verification.get("zip_sha256") or "")
            if not verification_zip_sha256:
                blockers.append(_blocker("governance_audit_verification_zip_sha256_missing", "Portfolio Governance Audit verification report is missing audit ZIP sha256."))
            elif not audit_binding.get("zip_exists"):
                blockers.append(_blocker("governance_audit_zip_missing", "Current Portfolio Governance Audit ZIP is missing."))
            elif verification_zip_sha256 != str(audit_binding.get("zip_sha256") or ""):
                blockers.append(_blocker("governance_audit_verification_zip_sha256", "Portfolio Governance Audit verification report does not match the current audit ZIP. Re-run audit verification."))
            verification_zip_size = _int_or_none(audit_verification.get("zip_size_bytes"))
            if verification_zip_size is None:
                blockers.append(_blocker("governance_audit_verification_zip_size_bytes_missing", "Portfolio Governance Audit verification report is missing audit ZIP size."))
            elif audit_binding.get("zip_exists") and verification_zip_size != audit_binding.get("zip_size_bytes"):
                blockers.append(_blocker("governance_audit_verification_zip_size_bytes", "Portfolio Governance Audit verification report ZIP size does not match the current audit ZIP. Re-run audit verification."))
            verification_manifest_hash = str(audit_verification.get("manifest_hash") or "")
            if not verification_manifest_hash:
                blockers.append(_blocker("governance_audit_verification_manifest_hash_missing", "Portfolio Governance Audit verification report is missing audit export manifest hash."))
            elif not audit_binding.get("manifest_hash"):
                blockers.append(_blocker("governance_audit_export_manifest_missing", "Current Portfolio Governance Audit export manifest is missing."))
            elif verification_manifest_hash != str(audit_binding.get("manifest_hash") or ""):
                blockers.append(_blocker("governance_audit_verification_manifest_hash", "Portfolio Governance Audit verification report does not match the current audit export manifest. Re-run audit verification."))
        if _reset_causality_status(ledger_entries) == "failed":
            blockers.append(_blocker("governance_reset_causality_failed", "Governance reset entries are not bound to applied Change Requests."))
        for item in audit_report.get("blockers", []) if isinstance(audit_report.get("blockers"), list) else []:
            if isinstance(item, dict):
                blockers.append(_blocker(f"audit_{item.get('check_id') or 'blocker'}", str(item.get("message") or "Governance Audit blocker.")))
        coverage = audit_report.get("coverage") if isinstance(audit_report.get("coverage"), dict) else {}
        if int(coverage.get("force_signed_count") or 0) > 0:
            warnings.append(_warning("force_signed_governance_queue", "At least one Governance Queue was force signed."))
        if int(coverage.get("reset_count") or 0) > 0:
            warnings.append(_warning("governance_signoff_reset_present", "At least one Governance Signoff reset is present."))
        if _redaction_summary({"audit_report": audit_report, "ledger": ledger_entries}).get("status") == "failed":
            blockers.append(_blocker("governance_reviewer_source_redaction", "Portfolio Governance reviewer source evidence contains sensitive values."))
        return blockers, warnings

    def _current_audit_package_binding(self, portfolio_id: str) -> dict[str, Any]:
        zip_path = self.audit_store.zip_path(portfolio_id)
        zip_exists = zip_path.exists() and zip_path.is_file() and not zip_path.is_symlink()
        audit_export_manifest = _read_optional_json(self.audit_store.export_dir(portfolio_id) / "manifest.json")
        return {
            "zip_exists": zip_exists,
            "zip_sha256": _sha256(zip_path) if zip_exists else None,
            "zip_size_bytes": zip_path.stat().st_size if zip_exists else None,
            "manifest_hash": audit_export_manifest.get("integrity_hash") if audit_export_manifest else None,
        }


def build_evidence_index(*, portfolio_id: str, source_hash: str, audit_report: dict[str, Any], ledger_entries: list[dict[str, Any]], audit_verification: dict[str, Any], audit_export_manifest: dict[str, Any], generated_at: str) -> dict[str, Any]:
    items: list[dict[str, Any]] = [
        {"name": "Portfolio Governance Audit Report", "type": "json", "status": audit_report.get("status") or "missing", "hash": audit_report.get("integrity_hash"), "required": True},
        {"name": "Portfolio Governance Audit Ledger", "type": "jsonl", "status": "passed" if ledger_entries and audit_ledger_integrity_ok(ledger_entries) else "failed", "hash": audit_report.get("ledger_hash"), "required": True},
        {"name": "Portfolio Governance Audit Verification", "type": "json", "status": audit_verification.get("status") or "missing", "hash": stable_hash(audit_verification) if audit_verification else None, "required": True},
        {"name": "Portfolio Governance Audit Export Manifest", "type": "json", "status": "passed" if audit_export_manifest else "missing", "hash": audit_export_manifest.get("integrity_hash") if audit_export_manifest else None, "required": False},
    ]
    for entry in ledger_entries[:120]:
        items.append(
            {
                "name": str(entry.get("event_type") or "governance_event"),
                "type": str(entry.get("domain") or "ledger"),
                "status": "failed" if entry.get("integrity_ok") is False or entry.get("stale") else "passed",
                "hash": (entry.get("source") if isinstance(entry.get("source"), dict) else {}).get("payload_hash"),
                "queue_id": entry.get("queue_id"),
                "event_at": entry.get("event_at"),
                "required": False,
            }
        )
    report = {
        "schema_version": PORTFOLIO_GOVERNANCE_REVIEWER_PACK_SCHEMA_VERSION,
        "portfolio_id": portfolio_id,
        "generated_at": generated_at,
        "source_hash": source_hash,
        "summary": {"item_count": len(items), "required_count": sum(1 for item in items if item.get("required"))},
        "items": items,
    }
    report["integrity_hash"] = evidence_index_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)


def build_timeline(*, portfolio_id: str, source_hash: str, ledger_entries: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    events = [
        {
            "event_at": item.get("event_at"),
            "sequence": item.get("sequence"),
            "domain": item.get("domain"),
            "event_type": item.get("event_type"),
            "queue_id": item.get("queue_id"),
            "status": "failed" if item.get("integrity_ok") is False or item.get("stale") else "passed",
            "entry_hash": item.get("entry_hash"),
        }
        for item in ledger_entries
    ]
    report = {
        "schema_version": PORTFOLIO_GOVERNANCE_REVIEWER_PACK_SCHEMA_VERSION,
        "portfolio_id": portfolio_id,
        "generated_at": generated_at,
        "source_hash": source_hash,
        "summary": {"event_count": len(events), "queue_count": len({str(item.get("queue_id") or "") for item in ledger_entries if item.get("queue_id")})},
        "events": events,
    }
    report["integrity_hash"] = timeline_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)


def build_retrospective_report(*, portfolio_id: str, source_hash: str, audit_report: dict[str, Any], ledger_entries: list[dict[str, Any]], timeline: dict[str, Any], warnings: list[dict[str, Any]], blockers: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    coverage = audit_report.get("coverage") if isinstance(audit_report.get("coverage"), dict) else {}
    recommendations = _recommendations(coverage, warnings, blockers)
    report = {
        "schema_version": PORTFOLIO_GOVERNANCE_REVIEWER_PACK_SCHEMA_VERSION,
        "portfolio_id": portfolio_id,
        "generated_at": generated_at,
        "source_hash": source_hash,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": {
            "queue_count": int(coverage.get("queue_count") or 0),
            "signed_queue_count": int(coverage.get("signed_queue_count") or 0),
            "archive_verified_count": int(coverage.get("archive_verified_count") or 0),
            "force_signed_count": int(coverage.get("force_signed_count") or 0),
            "reset_count": int(coverage.get("reset_count") or 0),
            "recommendation_count": len(recommendations),
            "timeline_event_count": (timeline.get("summary") if isinstance(timeline.get("summary"), dict) else {}).get("event_count", 0),
        },
        "timeline": timeline.get("events", [])[:200] if isinstance(timeline.get("events"), list) else [],
        "risk_hotspots": _risk_hotspots(ledger_entries, warnings, blockers),
        "recommendations": recommendations,
        "warnings": warnings,
        "blockers": blockers,
    }
    report["integrity_hash"] = retrospective_report_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)





def reviewer_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == reviewer_report_integrity_hash(data)





def retrospective_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == retrospective_report_integrity_hash(data)





def evidence_index_integrity_ok(index: dict[str, Any] | None) -> bool:
    data = index if isinstance(index, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_index_integrity_hash(data)





def timeline_integrity_ok(timeline: dict[str, Any] | None) -> bool:
    data = timeline if isinstance(timeline, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == timeline_integrity_hash(data)





def reviewer_pack_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == reviewer_pack_manifest_integrity_hash(data)


def reviewer_pack_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "readiness": data.get("readiness"),
            "portfolio_id": data.get("portfolio_id"),
            "source_hash": data.get("source_hash"),
            "integrity_ok": reviewer_report_integrity_ok(data),
            "audit_status": summary.get("audit_status"),
            "audit_package_verification_status": summary.get("audit_package_verification_status"),
            "queue_count": summary.get("queue_count", 0),
            "signed_queue_count": summary.get("signed_queue_count", 0),
            "archive_verified_count": summary.get("archive_verified_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS,
    )


def _reset_causality_status(entries: list[dict[str, Any]]) -> str:
    resets = [item for item in entries if item.get("event_type") in {"governance_signoff_reset", "governance_signoff_history_reset", "governance_queue_governance_signoff_reset"}]
    if not resets:
        return "not_applicable"
    applied_ids = {
        str((item.get("source") if isinstance(item.get("source"), dict) else {}).get("id") or "")
        for item in entries
        if item.get("event_type") == "governance_change_request_applied"
    }
    for item in resets:
        refs = item.get("causal_refs") if isinstance(item.get("causal_refs"), list) else []
        request_ids = {str(ref.get("id") or "") for ref in refs if isinstance(ref, dict) and ref.get("type") == "change_request"}
        if not request_ids or not (request_ids & applied_ids):
            return "failed"
    return "passed"


def _risk_summary(audit_report: dict[str, Any], ledger_entries: list[dict[str, Any]], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = audit_report.get("coverage") if isinstance(audit_report.get("coverage"), dict) else {}
    return {
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "force_signed_count": int(coverage.get("force_signed_count") or 0),
        "reset_count": int(coverage.get("reset_count") or 0),
        "failed_evidence_count": sum(1 for item in ledger_entries if item.get("integrity_ok") is False),
        "stale_evidence_count": sum(1 for item in ledger_entries if item.get("stale")),
    }


def _risk_hotspots(ledger_entries: list[dict[str, Any]], warnings: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in ledger_entries:
        if item.get("integrity_ok") is False:
            counts["integrity_failed"] = counts.get("integrity_failed", 0) + 1
        if item.get("stale"):
            counts["stale_evidence"] = counts.get("stale_evidence", 0) + 1
        if "force" in str(item.get("event_type") or ""):
            counts["force_signoff"] = counts.get("force_signoff", 0) + 1
        if "reset" in str(item.get("event_type") or ""):
            counts["reset"] = counts.get("reset", 0) + 1
    if blockers:
        counts["blockers"] = len(blockers)
    if warnings:
        counts["warnings"] = len(warnings)
    return [{"risk": key, "count": value, "severity": "blocking" if key in {"integrity_failed", "stale_evidence", "blockers"} else "warning"} for key, value in sorted(counts.items())]


def _recommendations(coverage: dict[str, Any], warnings: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if blockers:
        rows.append({"recommendation": "Resolve blocking Governance Audit evidence before sending the reviewer pack.", "priority": "high"})
    if int(coverage.get("force_signed_count") or 0) > 0:
        rows.append({"recommendation": "Review force-signed Governance Queues and confirm follow-up ownership.", "priority": "medium"})
    if int(coverage.get("reset_count") or 0) > 0:
        rows.append({"recommendation": "Review reset Change Request causality and applied reset hashes.", "priority": "medium"})
    if warnings and not rows:
        rows.append({"recommendation": "Review warning findings before external handoff.", "priority": "low"})
    if not rows:
        rows.append({"recommendation": "No deterministic governance follow-up is required.", "priority": "low"})
    return rows


def _reviewer_guide(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# MusicForge Portfolio Governance Reviewer Guide",
        "",
        f"Portfolio: {summary.get('portfolio_name') or report.get('portfolio_id')}",
        f"Status: {report.get('status')}",
        f"Readiness: {report.get('readiness')}",
        "",
        "## Scope",
        "This pack summarizes Portfolio Governance Audit evidence for external review. It does not include credentials, provider raw responses, audio, artwork, delivery ZIPs, or platform account data.",
        "",
        "## Key Evidence",
        f"- Governance audit status: {summary.get('audit_status')}",
        f"- Audit package verification: {summary.get('audit_package_verification_status')}",
        f"- Queues: {summary.get('queue_count', 0)}",
        f"- Signed queues: {summary.get('signed_queue_count', 0)}",
        f"- Verified archives: {summary.get('archive_verified_count', 0)}",
        f"- Force signed queues: {summary.get('force_signed_queue_count', 0)}",
        f"- Resets: {summary.get('reset_count', 0)}",
        "",
        "## Offline Verification",
        str((report.get("verification_instructions") or {}).get("command") or "verify-release-portfolio-governance-reviewer-pack portfolio-governance-reviewer-pack.zip"),
        "",
        "## Blockers",
    ]
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    lines.extend([f"- {item.get('check_id')}: {item.get('message')}" for item in blockers] or ["- None"])
    lines.append("")
    lines.append("## Warnings")
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    lines.extend([f"- {item.get('check_id')}: {item.get('message')}" for item in warnings] or ["- None"])
    return "\n".join(lines) + "\n"


def _retrospective_markdown(report: dict[str, Any]) -> str:
    lines = ["# MusicForge Portfolio Governance Retrospective", "", f"Status: {report.get('status')}", "", "## Timeline"]
    for item in report.get("timeline", [])[:60] if isinstance(report.get("timeline"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('event_at')} | {item.get('domain')} | {item.get('event_type')} | {item.get('status')}")
    lines.append("")
    lines.append("## Risk Hotspots")
    for item in report.get("risk_hotspots", []) if isinstance(report.get("risk_hotspots"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('risk')}: {item.get('count')} ({item.get('severity')})")
    lines.append("")
    lines.append("## Recommendations")
    recommendations = report.get("recommendations") if isinstance(report.get("recommendations"), list) else []
    lines.extend([f"- {item.get('recommendation')}" for item in recommendations if isinstance(item, dict)] or ["- No deterministic recommendations."])
    return "\n".join(lines) + "\n"


def _evidence_index_markdown(index: dict[str, Any]) -> str:
    lines = ["# Portfolio Governance Evidence Index", ""]
    for item in index.get("items", []) if isinstance(index.get("items"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('name')} | {item.get('type')} | {item.get('status')} | {item.get('hash') or '-'}")
    return "\n".join(lines) + "\n"


def _timeline_markdown(timeline: dict[str, Any]) -> str:
    lines = ["# Portfolio Governance Timeline", ""]
    for item in timeline.get("events", []) if isinstance(timeline.get("events"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('event_at')} | #{item.get('sequence')} | {item.get('domain')} | {item.get('event_type')} | {item.get('status')}")
    return "\n".join(lines) + "\n"


def _report_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return "\n".join(
        [
            "# Portfolio Governance Reviewer Report",
            "",
            f"Portfolio: {report.get('portfolio_id')}",
            f"Status: {report.get('status')}",
            f"Audit: {summary.get('audit_status')}",
            f"Queues: {summary.get('queue_count', 0)}",
            f"Signed Queues: {summary.get('signed_queue_count', 0)}",
            f"Verified Archives: {summary.get('archive_verified_count', 0)}",
        ]
    ) + "\n"


def _write_readme(export_dir: Path, report: dict[str, Any]) -> None:
    lines = [
        "MusicForge Release Portfolio Governance Reviewer Pack",
        "",
        f"Portfolio ID: {report.get('portfolio_id')}",
        f"Status: {report.get('status')}",
        "",
        "Open REVIEWER_GUIDE.md for external review instructions and RETROSPECTIVE.md for internal process notes.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {"status": report.get("status") or "missing", "summary": summary}


def _read_json_or_default(path: Path, default: dict[str, Any] | None) -> dict[str, Any]:
    if not path.exists():
        return default if default is not None else {}
    value = read_json(path)
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except Exception:
        return {}
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS))


def _file_record(export_dir: Path, path: Path) -> dict[str, Any]:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(export_dir.resolve(), resolved)
        entry = _validate_relative_path(resolved.relative_to(export_dir.resolve()).as_posix())
        if entry in seen:
            raise ReleasePortfolioGovernanceReviewerPackStateError(f"Duplicate Portfolio Governance Reviewer Pack ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleasePortfolioGovernanceReviewerPackStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleasePortfolioGovernanceReviewerPackStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleasePortfolioGovernanceReviewerPackStateError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceReviewerPackStateError("Refusing to operate outside Portfolio Governance Reviewer Pack boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _redaction_summary(value: Any) -> dict[str, Any]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}


def _blocker(check_id: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": "warning", "message": message}
