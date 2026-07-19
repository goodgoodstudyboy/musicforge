# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

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
from song_agent.domains.trust.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore as ReleasePortfolioGovernanceEvidenceVaultStore, evidence_vault_manifest_integrity_ok as evidence_vault_manifest_integrity_ok, evidence_vault_report_integrity_hash as evidence_vault_report_integrity_hash, evidence_vault_report_integrity_ok as evidence_vault_report_integrity_ok, evidence_vault_verification_summary as evidence_vault_verification_summary
from song_agent.domains.trust.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore as ReleasePortfolioGovernanceFinalBoardStore, final_board_report_integrity_hash as final_board_report_integrity_hash, final_board_report_integrity_ok as final_board_report_integrity_ok, final_board_signoff_hash as final_board_signoff_hash, final_board_signoff_integrity_ok as final_board_signoff_integrity_ok
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_contracts import ATTESTATION_BLOCKED_KEYS as ATTESTATION_BLOCKED_KEYS, ATTESTATION_CERTIFICATE_HASH_EXCLUDE_KEYS as ATTESTATION_CERTIFICATE_HASH_EXCLUDE_KEYS, ATTESTATION_CERTIFICATE_TYPE as ATTESTATION_CERTIFICATE_TYPE, ATTESTATION_MANIFEST_HASH_EXCLUDE_KEYS as ATTESTATION_MANIFEST_HASH_EXCLUDE_KEYS, ATTESTATION_PACKAGE_TYPE as ATTESTATION_PACKAGE_TYPE, ATTESTATION_REPORT_HASH_EXCLUDE_KEYS as ATTESTATION_REPORT_HASH_EXCLUDE_KEYS, attestation_certificate_hash as attestation_certificate_hash, attestation_manifest_hash as attestation_manifest_hash, attestation_report_integrity_hash as attestation_report_integrity_hash, attestation_verification_summary as attestation_verification_summary


ATTESTATION_SCHEMA_VERSION = 1
ATTESTATION_EXPORT_SCHEMA_VERSION = 1

ATTESTATION_REPORT_PACKAGE_TYPE = "release_portfolio_governance_attestation_report"





SIGNED_STATUSES = {"signed", "force_signed"}
ATTESTATION_PROFILES = {"public_summary", "partner_due_diligence", "internal_public_preview"}


class ReleasePortfolioGovernanceAttestationError(ValueError):
    pass


class ReleasePortfolioGovernanceAttestationNotFoundError(ReleasePortfolioGovernanceAttestationError):
    pass


class ReleasePortfolioGovernanceAttestationStateError(ReleasePortfolioGovernanceAttestationError):
    pass


class ReleasePortfolioGovernanceAttestationStore:
    def __init__(
        self,
        *,
        portfolio_store: ReleasePortfolioAuditStore,
        final_board_store: ReleasePortfolioGovernanceFinalBoardStore,
        evidence_vault_store: ReleasePortfolioGovernanceEvidenceVaultStore,
    ) -> None:
        self.portfolio_store = portfolio_store
        self.final_board_store = final_board_store
        self.evidence_vault_store = evidence_vault_store
        self.lock = threading.RLock()

    def root_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        profile = _validate_profile(profile)
        root = self.portfolio_store.portfolio_dir(portfolio_id) / "governance-attestation"
        if profile == "public_summary":
            return root
        return root / "profiles" / profile

    def report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "attestation-report.json"

    def certificate_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "certificate.json"

    def certificate_md_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "certificate.md"

    def certificate_html_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "certificate.html"

    def history_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "attestation-history.jsonl"

    def export_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "export"

    def zip_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "portfolio-governance-public-attestation.zip"

    def verification_report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "verification-report.json"

    def read_report(self, portfolio_id: str, *, profile: str = "public_summary", default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.report_path(portfolio_id, profile), default=default)

    def read_certificate(self, portfolio_id: str, *, profile: str = "public_summary", default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.certificate_path(portfolio_id, profile), default=default)

    def read_export_manifest(self, portfolio_id: str, *, profile: str = "public_summary") -> DomainDocument:
        path = self.export_dir(portfolio_id, profile) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceAttestationNotFoundError("Portfolio Governance Public Attestation export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(_as_document(value), blocked_keys=ATTESTATION_BLOCKED_KEYS)

    def refresh_report(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = _validate_profile(str(payload.get("profile") or "public_summary"))
            self.portfolio_store.get_portfolio(portfolio_id)
            source = self.build_source(portfolio_id, profile=profile)
            blockers, warnings, checks = self._findings(source, payload)
            summary = _summary_from_source(source, blockers, warnings)
            report = {
                "schema_version": ATTESTATION_SCHEMA_VERSION,
                "package_type": ATTESTATION_REPORT_PACKAGE_TYPE,
                "report_id": self._reserve_report_id(portfolio_id, profile),
                "portfolio_id": portfolio_id,
                "generated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "readiness": "blocked" if blockers else "attestation_ready",
                "source_hash": stable_hash(source),
                "source": source,
                "summary": summary,
                "blockers": blockers,
                "warnings": warnings,
                "checks": checks,
            }
            report["integrity_hash"] = attestation_report_integrity_hash(report)
            certificate = build_certificate(report=report, generated_at=now, profile=profile)
            root = self.root_dir(portfolio_id, profile)
            root.mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(portfolio_id, profile), sanitize_metadata(report, blocked_keys=ATTESTATION_BLOCKED_KEYS))
            _write_json(self.certificate_path(portfolio_id, profile), certificate)
            self.certificate_md_path(portfolio_id, profile).write_text(_certificate_markdown(certificate), encoding="utf-8")
            self.certificate_html_path(portfolio_id, profile).write_text(_certificate_html(certificate), encoding="utf-8")
            self._append_history(portfolio_id, profile, "report_refreshed", {"status": report["status"], "report_id": report["report_id"], "source_hash": report["source_hash"], "profile": profile}, now=now)
            return sanitize_metadata(report, blocked_keys=ATTESTATION_BLOCKED_KEYS)

    def build_source(self, portfolio_id: str, *, profile: str = "public_summary") -> DomainDocument:
        profile = _validate_profile(profile)
        portfolio = self.portfolio_store.get_portfolio(portfolio_id)
        portfolio_report = self.portfolio_store.read_report(portfolio_id, default={})
        final_report = self.final_board_store.read_report(portfolio_id, default={})
        final_signoff = self.final_board_store.read_signoff(portfolio_id, default={})
        final_summary = self.final_board_store.signoff_summary(portfolio_id, signoff=final_signoff) if final_signoff else {}
        vault_report = self.evidence_vault_store.read_report(portfolio_id, default={})
        vault_manifest = _read_json_default(self.evidence_vault_store.export_dir(portfolio_id) / "manifest.json", default={})
        vault_verification = _read_json_default(self.evidence_vault_store.verification_report_path(portfolio_id), default={})
        vault_zip_path = self.evidence_vault_store.zip_path(portfolio_id)
        reviewer_status = ((_as_document(final_report.get("summary"))) or {}).get("reviewer_response_status")
        source = {
            "portfolio_id": portfolio_id,
            "portfolio_hash": stable_hash(portfolio),
            "portfolio_name_hash": stable_hash(str(portfolio.get("name") or "")),
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
            "final_board_signoff_status": final_summary.get("status") or final_signoff.get("status") if final_signoff else "missing",
            "final_board_signoff_integrity_ok": final_board_signoff_integrity_ok(final_signoff) if final_signoff else False,
            "final_board_signoff_stale": bool(final_summary.get("stale")) if final_summary else True,
            "final_board_signoff_force": bool(final_signoff.get("force")),
            "evidence_vault_report_hash": evidence_vault_report_integrity_hash(vault_report) if vault_report else None,
            "evidence_vault_report_integrity_hash": vault_report.get("integrity_hash") if vault_report else None,
            "evidence_vault_report_integrity_ok": evidence_vault_report_integrity_ok(vault_report) if vault_report else False,
            "evidence_vault_report_status": vault_report.get("status") if vault_report else "missing",
            "evidence_vault_report_stale": self.evidence_vault_store.report_is_stale(portfolio_id, vault_report) if vault_report else False,
            "evidence_vault_source_hash": vault_report.get("source_hash") if vault_report else None,
            "evidence_vault_zip_exists": vault_zip_path.exists() and vault_zip_path.is_file() and not vault_zip_path.is_symlink(),
            "evidence_vault_zip_sha256": _sha256(vault_zip_path) if vault_zip_path.exists() else None,
            "evidence_vault_zip_size_bytes": vault_zip_path.stat().st_size if vault_zip_path.exists() else None,
            "evidence_vault_manifest_hash": vault_manifest.get("integrity_hash") if vault_manifest else None,
            "evidence_vault_manifest_integrity_ok": evidence_vault_manifest_integrity_ok(vault_manifest) if vault_manifest else False,
            "evidence_vault_verification_hash": stable_hash(vault_verification) if vault_verification else None,
            "evidence_vault_verification_status": vault_verification.get("status") if vault_verification else "missing",
            "evidence_vault_verification_zip_sha256": vault_verification.get("zip_sha256") if vault_verification else None,
            "evidence_vault_verification_zip_size_bytes": vault_verification.get("zip_size_bytes") if vault_verification else None,
            "evidence_vault_verification_manifest_hash": vault_verification.get("manifest_hash") if vault_verification else None,
            "evidence_vault_deep_verification_status": (_as_document(vault_verification.get("summary"))).get("deep_verification_status") if vault_verification else "missing",
            "signed_queue_count": int((_as_document(vault_report.get("summary"))).get("signed_queue_count") or 0),
            "force_signed_queue_count": int((_as_document(vault_report.get("summary"))).get("force_signed_queue_count") or 0),
            "reviewer_response_status": reviewer_status or "unknown",
            "attestation_profile": profile,
        }
        return sanitize_metadata(source, blocked_keys=ATTESTATION_BLOCKED_KEYS)

    def report_is_stale(self, portfolio_id: str, report: DomainDocument | None = None, *, profile: str = "public_summary") -> bool:
        data = _document_or(report, self.read_report(portfolio_id, profile=profile, default={}))
        if not data:
            return False
        try:
            source = self.build_source(portfolio_id, profile=str((_as_document(data.get("source"))).get("attestation_profile") or profile))
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_attestation(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = _validate_profile(str(payload.get("profile") or "public_summary"))
            report = self.read_report(portfolio_id, profile=profile, default={}) or self.refresh_report(portfolio_id, {"profile": profile}, now=now)
            certificate = self.read_certificate(portfolio_id, profile=profile, default={})
            source = self.build_source(portfolio_id, profile=profile)
            self._ensure_exportable(portfolio_id, profile, report, certificate, source, payload)
            triple = _immutability_triple(source)
            if self._history_has_current_triple_event(portfolio_id, profile, triple, "attestation_exported"):
                raise ReleasePortfolioGovernanceAttestationStateError("Public Attestation export already exists for this Evidence Vault, Final Board signoff, and profile.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            existing_manifest = _read_json_default(export_dir / "manifest.json", default={})
            if _manifest_triple(existing_manifest) == triple:
                raise ReleasePortfolioGovernanceAttestationStateError("Public Attestation export already exists for this Evidence Vault, Final Board signoff, and profile.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            _write_json(export_dir / "attestation-report.json", report)
            _write_json(export_dir / "certificate.json", certificate)
            (export_dir / "certificate.md").write_text(_certificate_markdown(certificate), encoding="utf-8")
            (export_dir / "certificate.html").write_text(_certificate_html(certificate), encoding="utf-8")
            _write_readme(export_dir, certificate)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest = {
                "schema_version": ATTESTATION_EXPORT_SCHEMA_VERSION,
                "package_type": ATTESTATION_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Release Portfolio Governance Public Attestation", "version": __version__},
                "portfolio_id": portfolio_id,
                "created_at": now,
                "source_hash": report.get("source_hash"),
                "attestation_profile": profile,
                "attestation_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "certificate": {"certificate_id": certificate.get("certificate_id"), "payload_hash": certificate.get("payload_hash")},
                "final_board": {"signoff_hash": source.get("final_board_signoff_hash"), "signoff_status": source.get("final_board_signoff_status")},
                "evidence_vault": _evidence_vault_manifest_row(source),
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"report": report, "certificate": certificate}),
            }
            manifest["integrity_hash"] = attestation_manifest_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
            self._append_history(portfolio_id, profile, "attestation_exported", {"profile": profile, **triple, "manifest_hash": manifest["integrity_hash"], "file_count": len(files)}, now=now)
            return sanitize_metadata(manifest, blocked_keys=ATTESTATION_BLOCKED_KEYS)

    def build_zip(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = _validate_profile(str(payload.get("profile") or "public_summary"))
            report = self.read_report(portfolio_id, profile=profile, default={})
            certificate = self.read_certificate(portfolio_id, profile=profile, default={})
            source = self.build_source(portfolio_id, profile=profile)
            self._ensure_exportable(portfolio_id, profile, report, certificate, source, payload)
            triple = _immutability_triple(source)
            if self._history_has_current_triple_event(portfolio_id, profile, triple, "attestation_zip_built"):
                raise ReleasePortfolioGovernanceAttestationStateError("Public Attestation ZIP already exists for this Evidence Vault, Final Board signoff, and profile.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            zip_path = self.zip_path(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "manifest.json").exists():
                if self._history_has_current_triple_event(portfolio_id, profile, triple, "attestation_exported"):
                    raise ReleasePortfolioGovernanceAttestationStateError("Public Attestation export already exists for this Evidence Vault, Final Board signoff, and profile.")
                self.export_attestation(portfolio_id, {"profile": profile}, now=now)
            if zip_path.exists():
                manifest_in_zip = _read_zip_json(zip_path, "manifest.json")
                if _manifest_triple(manifest_in_zip) == triple:
                    raise ReleasePortfolioGovernanceAttestationStateError("Public Attestation ZIP already exists for this Evidence Vault, Final Board signoff, and profile.")
            manifest = read_json(export_dir / "manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = attestation_manifest_hash(manifest)
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
            self._append_history(portfolio_id, profile, "attestation_zip_built", {"profile": profile, **triple, "sha256": info["sha256"], "entry_count": len(entries)}, now=now)
            return sanitize_metadata(info, blocked_keys=ATTESTATION_BLOCKED_KEYS)

    def summary(self, portfolio_id: str, *, profile: str = "public_summary") -> DomainDocument:
        report = self.read_report(portfolio_id, profile=profile, default={})
        certificate = self.read_certificate(portfolio_id, profile=profile, default={})
        verification = _read_json_default(self.verification_report_path(portfolio_id, profile), default={})
        if not report:
            return {"status": "missing", "profile": profile, "verification_status": verification.get("status") or "missing"}
        summary = attestation_summary(report)
        summary["stale"] = self.report_is_stale(portfolio_id, report, profile=profile)
        summary["certificate_id"] = certificate.get("certificate_id")
        summary["certificate_payload_hash"] = certificate.get("payload_hash")
        summary["zip_sha256"] = _sha256(self.zip_path(portfolio_id, profile)) if self.zip_path(portfolio_id, profile).exists() else None
        summary["verification_status"] = verification.get("status") or "missing"
        return sanitize_metadata(summary, blocked_keys=ATTESTATION_BLOCKED_KEYS)

    def _findings(self, source: ImplementationDocument, payload: ImplementationDocument) -> tuple[list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
        blockers: list[ImplementationDocument] = []
        warnings: list[ImplementationDocument] = []
        checks: list[ImplementationDocument] = []

        def check(check_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            status = "passed" if passed else "warning" if warning else "failed"
            row = {"check_id": check_id, "status": status, "severity": "warning" if warning else "blocking", "message": message}
            checks.append(row)
            if passed:
                return
            if warning:
                warnings.append(_warning(check_id, message))
            else:
                blockers.append(_blocker(check_id, message))

        check("portfolio_report_current", bool(source.get("portfolio_report_integrity_ok")) and not source.get("portfolio_report_stale"), "Portfolio Audit report is current.")
        check("final_board_report_current", bool(source.get("final_board_report_integrity_ok")) and not source.get("final_board_report_stale") and source.get("final_board_report_status") != "failed", "Final Board report is current.")
        check("final_board_signoff_current", source.get("final_board_signoff_status") in SIGNED_STATUSES and bool(source.get("final_board_signoff_integrity_ok")) and not source.get("final_board_signoff_stale"), "Final Board signoff is signed and current.")
        check("evidence_vault_report_current", bool(source.get("evidence_vault_report_integrity_ok")) and not source.get("evidence_vault_report_stale") and source.get("evidence_vault_report_status") == "passed", "Evidence Vault report is current and passed.")
        check("evidence_vault_zip_exists", bool(source.get("evidence_vault_zip_exists")), "Evidence Vault ZIP exists.")
        check("evidence_vault_manifest_current", bool(source.get("evidence_vault_manifest_integrity_ok")), "Evidence Vault export manifest integrity is valid.")
        check(
            "evidence_vault_verification_current",
            source.get("evidence_vault_verification_status") == "passed"
            and source.get("evidence_vault_deep_verification_status") == "passed"
            and source.get("evidence_vault_verification_zip_sha256") == source.get("evidence_vault_zip_sha256")
            and source.get("evidence_vault_verification_zip_size_bytes") == source.get("evidence_vault_zip_size_bytes")
            and source.get("evidence_vault_verification_manifest_hash") == source.get("evidence_vault_manifest_hash"),
            "Evidence Vault verification report matches the current Vault ZIP and manifest.",
        )
        if bool(source.get("final_board_signoff_force")) or int(source.get("force_signed_queue_count") or 0) > 0:
            check("force_evidence_present", False, "Force-signed governance evidence is present.", warning=not bool(payload.get("require_no_force", False)))
        if _redaction_summary({"source": source}).get("status") == "failed":
            check("redaction_scan", False, "Public Attestation source contains sensitive values.")
        else:
            check("redaction_scan", True, "No sensitive values found in Public Attestation source.")
        return blockers, warnings, checks

    def _ensure_exportable(self, portfolio_id: str, profile: str, report: ImplementationDocument, certificate: ImplementationDocument, source: ImplementationDocument, payload: ImplementationDocument) -> None:
        if not report:
            raise ReleasePortfolioGovernanceAttestationStateError("Public Attestation Report does not exist. Refresh before export.")
        if not attestation_report_integrity_ok(report):
            raise ReleasePortfolioGovernanceAttestationStateError("Public Attestation Report integrity failed. Refresh before export.")
        if not attestation_certificate_integrity_ok(certificate):
            raise ReleasePortfolioGovernanceAttestationStateError("Public Attestation certificate integrity failed. Refresh before export.")
        if self.report_is_stale(portfolio_id, report, profile=profile) or str(report.get("source_hash") or "") != stable_hash(source):
            raise ReleasePortfolioGovernanceAttestationStateError("Public Attestation source is stale. Refresh before export.")
        blockers, _warnings, _checks = self._findings(source, payload)
        if blockers or report.get("status") == "failed":
            detail = str((blockers[0] if blockers else {}).get("message") or "Public Attestation Report is failed.")
            raise ReleasePortfolioGovernanceAttestationStateError(f"Public Attestation cannot be exported: {detail}")

    def _history_has_current_triple_event(self, portfolio_id: str, profile: str, triple: dict[str, str], event_type: str) -> bool:
        path = self.history_path(portfolio_id, profile)
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
            if all(str(summary.get(key) or "") == str(value or "") for key, value in triple.items()):
                return True
        return False

    def _reserve_report_id(self, portfolio_id: str, profile: str) -> str:
        existing = self.read_report(portfolio_id, profile=profile, default={})
        if str(existing.get("report_id") or "").startswith("pga-"):
            return str(existing.get("report_id"))
        return "pga-000001"

    def _append_history(self, portfolio_id: str, profile: str, event_type: str, summary: ImplementationDocument, *, now: str | None = None) -> None:
        path = self.history_path(portfolio_id, profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"pgae-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=ATTESTATION_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def build_certificate(*, report: DomainDocument, generated_at: str, profile: str) -> DomainDocument:
    source = _as_document(report.get("source"))
    certificate: _InferenceType = {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "certificate_id": "pgc-000001",
        "certificate_type": ATTESTATION_CERTIFICATE_TYPE,
        "portfolio_id": report.get("portfolio_id"),
        "issued_at": generated_at,
        "issuer": {"tool": "MusicForge", "version": __version__},
        "attestation_profile": profile,
        "governance_status": "passed" if report.get("status") == "passed" else report.get("status"),
        "final_board": {
            "signoff_status": source.get("final_board_signoff_status"),
            "signoff_hash": source.get("final_board_signoff_hash"),
            "report_hash": source.get("final_board_report_hash"),
        },
        "evidence_vault": _evidence_vault_manifest_row(source),
        "coverage": {
            "signed_queue_count": source.get("signed_queue_count"),
            "force_signed_queue_count": source.get("force_signed_queue_count"),
            "reviewer_response_status": source.get("reviewer_response_status"),
        },
        "public_notes": [],
        "verification": {"command": "python -m song_agent.cli verify-release-portfolio-governance-attestation portfolio-governance-public-attestation.zip --strict --require-vault --require-final-board --json"},
    }
    certificate["payload_hash"] = attestation_certificate_hash(certificate)
    return sanitize_metadata(certificate, blocked_keys=ATTESTATION_BLOCKED_KEYS)





def attestation_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == attestation_report_integrity_hash(data)





def attestation_certificate_integrity_ok(certificate: DomainDocument | None) -> bool:
    data = _as_document(certificate)
    return bool(data.get("payload_hash")) and str(data.get("payload_hash")) == attestation_certificate_hash(data)





def attestation_manifest_integrity_ok(manifest: DomainDocument | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == attestation_manifest_hash(data)


def attestation_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    if not data:
        return {"status": "missing", "integrity_ok": False}
    summary = _as_document(data.get("summary"))
    return sanitize_metadata({"status": data.get("status"), "readiness": data.get("readiness"), "profile": summary.get("attestation_profile"), "portfolio_id": data.get("portfolio_id"), "source_hash": data.get("source_hash"), "integrity_hash": data.get("integrity_hash"), "integrity_ok": attestation_report_integrity_ok(data), **summary}, blocked_keys=ATTESTATION_BLOCKED_KEYS)





def _summary_from_source(source: ImplementationDocument, blockers: list[ImplementationDocument], warnings: list[ImplementationDocument]) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "portfolio_id": source.get("portfolio_id"),
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "final_board_status": source.get("final_board_signoff_status"),
            "vault_verification_status": source.get("evidence_vault_verification_status"),
            "deep_verification_status": source.get("evidence_vault_deep_verification_status"),
            "vault_zip_sha256": source.get("evidence_vault_zip_sha256"),
            "signed_queue_count": source.get("signed_queue_count"),
            "force_signed_queue_count": source.get("force_signed_queue_count"),
            "reviewer_response_status": source.get("reviewer_response_status"),
            "attestation_profile": source.get("attestation_profile"),
            "certificate_status": "blocked" if blockers else "ready",
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        blocked_keys=ATTESTATION_BLOCKED_KEYS,
    )


def _evidence_vault_manifest_row(source: ImplementationDocument) -> ImplementationDocument:
    return {
        "zip_sha256": source.get("evidence_vault_zip_sha256"),
        "zip_size_bytes": source.get("evidence_vault_zip_size_bytes"),
        "manifest_hash": source.get("evidence_vault_manifest_hash"),
        "verification_hash": source.get("evidence_vault_verification_hash"),
        "verification_status": source.get("evidence_vault_verification_status"),
        "deep_verification_status": source.get("evidence_vault_deep_verification_status"),
    }


def _immutability_triple(source: ImplementationDocument) -> dict[str, str]:
    return {
        "evidence_vault_zip_sha256": str(source.get("evidence_vault_zip_sha256") or ""),
        "final_board_signoff_hash": str(source.get("final_board_signoff_hash") or ""),
        "attestation_profile": str(source.get("attestation_profile") or "public_summary"),
    }


def _manifest_triple(manifest: ImplementationDocument) -> dict[str, str]:
    evidence = _as_document(manifest.get("evidence_vault"))
    final_board = _as_document(manifest.get("final_board"))
    return {
        "evidence_vault_zip_sha256": str(evidence.get("zip_sha256") or ""),
        "final_board_signoff_hash": str(final_board.get("signoff_hash") or ""),
        "attestation_profile": str(manifest.get("attestation_profile") or "public_summary"),
    }


from song_agent.domains.trust import v142_rpga_readiness as _v142_rpga_readiness
from song_agent.domains.trust.v142_rpga_readiness import (
    _certificate_markdown,
    _certificate_html,
    _write_readme,
    _file_record,
    _zip_entries,
    _read_zip_json,
    _read_json_default,
    _write_json,
    _sha256,
    _ensure_within,
    _redaction_summary,
    _blocker,
    _warning,
    _validate_profile,
)

_v142_rpga_readiness.bind_globals(globals())
