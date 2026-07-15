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
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore, portfolio_report_integrity_hash, portfolio_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore, evidence_vault_manifest_integrity_ok, evidence_vault_report_integrity_hash, evidence_vault_report_integrity_ok, evidence_vault_verification_summary
from song_agent.domains.trust.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore, final_board_report_integrity_hash, final_board_report_integrity_ok, final_board_signoff_hash, final_board_signoff_integrity_ok
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_contracts import ATTESTATION_BLOCKED_KEYS, ATTESTATION_CERTIFICATE_HASH_EXCLUDE_KEYS, ATTESTATION_CERTIFICATE_TYPE, ATTESTATION_MANIFEST_HASH_EXCLUDE_KEYS, ATTESTATION_PACKAGE_TYPE, ATTESTATION_REPORT_HASH_EXCLUDE_KEYS, attestation_certificate_hash, attestation_manifest_hash, attestation_report_integrity_hash, attestation_verification_summary


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

    def read_report(self, portfolio_id: str, *, profile: str = "public_summary", default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(portfolio_id, profile), default=default)

    def read_certificate(self, portfolio_id: str, *, profile: str = "public_summary", default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.certificate_path(portfolio_id, profile), default=default)

    def read_export_manifest(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        path = self.export_dir(portfolio_id, profile) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceAttestationNotFoundError("Portfolio Governance Public Attestation export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=ATTESTATION_BLOCKED_KEYS)

    def refresh_report(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def build_source(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
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
        reviewer_status = ((final_report.get("summary") if isinstance(final_report.get("summary"), dict) else {}) or {}).get("reviewer_response_status")
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
            "evidence_vault_deep_verification_status": (vault_verification.get("summary") if isinstance(vault_verification.get("summary"), dict) else {}).get("deep_verification_status") if vault_verification else "missing",
            "signed_queue_count": int((vault_report.get("summary") if isinstance(vault_report.get("summary"), dict) else {}).get("signed_queue_count") or 0),
            "force_signed_queue_count": int((vault_report.get("summary") if isinstance(vault_report.get("summary"), dict) else {}).get("force_signed_queue_count") or 0),
            "reviewer_response_status": reviewer_status or "unknown",
            "attestation_profile": profile,
        }
        return sanitize_metadata(source, blocked_keys=ATTESTATION_BLOCKED_KEYS)

    def report_is_stale(self, portfolio_id: str, report: dict[str, Any] | None = None, *, profile: str = "public_summary") -> bool:
        data = report if isinstance(report, dict) else self.read_report(portfolio_id, profile=profile, default={})
        if not data:
            return False
        try:
            source = self.build_source(portfolio_id, profile=str((data.get("source") if isinstance(data.get("source"), dict) else {}).get("attestation_profile") or profile))
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_attestation(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def build_zip(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def summary(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
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

    def _findings(self, source: dict[str, Any], payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []

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

    def _ensure_exportable(self, portfolio_id: str, profile: str, report: dict[str, Any], certificate: dict[str, Any], source: dict[str, Any], payload: dict[str, Any]) -> None:
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
            summary = event.get("summary") if isinstance(event.get("summary"), dict) else {}
            if all(str(summary.get(key) or "") == str(value or "") for key, value in triple.items()):
                return True
        return False

    def _reserve_report_id(self, portfolio_id: str, profile: str) -> str:
        existing = self.read_report(portfolio_id, profile=profile, default={})
        if str(existing.get("report_id") or "").startswith("pga-"):
            return str(existing.get("report_id"))
        return "pga-000001"

    def _append_history(self, portfolio_id: str, profile: str, event_type: str, summary: dict[str, Any], *, now: str | None = None) -> None:
        path = self.history_path(portfolio_id, profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"pgae-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=ATTESTATION_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def build_certificate(*, report: dict[str, Any], generated_at: str, profile: str) -> dict[str, Any]:
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    certificate = {
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





def attestation_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == attestation_report_integrity_hash(data)





def attestation_certificate_integrity_ok(certificate: dict[str, Any] | None) -> bool:
    data = certificate if isinstance(certificate, dict) else {}
    return bool(data.get("payload_hash")) and str(data.get("payload_hash")) == attestation_certificate_hash(data)





def attestation_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == attestation_manifest_hash(data)


def attestation_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    if not data:
        return {"status": "missing", "integrity_ok": False}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata({"status": data.get("status"), "readiness": data.get("readiness"), "profile": summary.get("attestation_profile"), "portfolio_id": data.get("portfolio_id"), "source_hash": data.get("source_hash"), "integrity_hash": data.get("integrity_hash"), "integrity_ok": attestation_report_integrity_ok(data), **summary}, blocked_keys=ATTESTATION_BLOCKED_KEYS)





def _summary_from_source(source: dict[str, Any], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
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


def _evidence_vault_manifest_row(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "zip_sha256": source.get("evidence_vault_zip_sha256"),
        "zip_size_bytes": source.get("evidence_vault_zip_size_bytes"),
        "manifest_hash": source.get("evidence_vault_manifest_hash"),
        "verification_hash": source.get("evidence_vault_verification_hash"),
        "verification_status": source.get("evidence_vault_verification_status"),
        "deep_verification_status": source.get("evidence_vault_deep_verification_status"),
    }


def _immutability_triple(source: dict[str, Any]) -> dict[str, str]:
    return {
        "evidence_vault_zip_sha256": str(source.get("evidence_vault_zip_sha256") or ""),
        "final_board_signoff_hash": str(source.get("final_board_signoff_hash") or ""),
        "attestation_profile": str(source.get("attestation_profile") or "public_summary"),
    }


def _manifest_triple(manifest: dict[str, Any]) -> dict[str, str]:
    evidence = manifest.get("evidence_vault") if isinstance(manifest.get("evidence_vault"), dict) else {}
    final_board = manifest.get("final_board") if isinstance(manifest.get("final_board"), dict) else {}
    return {
        "evidence_vault_zip_sha256": str(evidence.get("zip_sha256") or ""),
        "final_board_signoff_hash": str(final_board.get("signoff_hash") or ""),
        "attestation_profile": str(manifest.get("attestation_profile") or "public_summary"),
    }


def _certificate_markdown(certificate: dict[str, Any]) -> str:
    final_board = certificate.get("final_board") if isinstance(certificate.get("final_board"), dict) else {}
    vault = certificate.get("evidence_vault") if isinstance(certificate.get("evidence_vault"), dict) else {}
    coverage = certificate.get("coverage") if isinstance(certificate.get("coverage"), dict) else {}
    return "\n".join(
        [
            "# MusicForge Portfolio Governance Public Attestation",
            "",
            f"Certificate ID: `{certificate.get('certificate_id')}`",
            f"Portfolio ID: `{certificate.get('portfolio_id')}`",
            f"Governance status: `{certificate.get('governance_status')}`",
            f"Final Board signoff status: `{final_board.get('signoff_status')}`",
            f"Final Board signoff hash: `{final_board.get('signoff_hash')}`",
            f"Evidence Vault ZIP SHA-256: `{vault.get('zip_sha256')}`",
            f"Evidence Vault verification: `{vault.get('verification_status')}` / deep `{vault.get('deep_verification_status')}`",
            f"Signed governance queues: `{coverage.get('signed_queue_count')}`",
            f"Force-signed governance queues: `{coverage.get('force_signed_queue_count')}`",
            "",
            "This public attestation contains hash fingerprints and summary evidence only. Request the full Evidence Vault for deep nested package verification.",
            "",
        ]
    )


def _certificate_html(certificate: dict[str, Any]) -> str:
    text = _certificate_markdown(certificate)
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"<!doctype html><html><head><meta charset=\"utf-8\"><title>MusicForge Public Attestation</title></head><body><pre>{escaped}</pre></body></html>"


def _write_readme(export_dir: Path, certificate: dict[str, Any]) -> None:
    (export_dir / "README.txt").write_text(
        "\n".join(
            [
                "MusicForge Release Portfolio Governance Public Attestation",
                "",
                f"Certificate ID: {certificate.get('certificate_id')}",
                "This package contains public summary evidence only.",
                "It does not contain Evidence Vault nested ZIP packages.",
                "Verify it with: python -m song_agent.cli verify-release-portfolio-governance-attestation portfolio-governance-public-attestation.zip --strict --require-vault --require-final-board --json",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rows.append((path.resolve(), path.relative_to(root).as_posix()))
    return rows


def _read_zip_json(zip_path: Path, entry: str) -> dict[str, Any]:
    if not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            return json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}


def _read_json_default(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return value if isinstance(value, dict) else dict(default or {})


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, payload)


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceAttestationStateError("Resolved path escapes Public Attestation directory.") from exc


def _redaction_summary(value: Any) -> dict[str, Any]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}


def _blocker(check_id: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": "warning", "message": message}


def _validate_profile(profile: str) -> str:
    value = str(profile or "public_summary").strip()
    if value not in ATTESTATION_PROFILES:
        raise ReleasePortfolioGovernanceAttestationError(f"Unsupported attestation profile: {value}")
    return value
