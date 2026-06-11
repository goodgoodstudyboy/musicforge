from __future__ import annotations

import html
import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text
from song_agent.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore
from song_agent.release_portfolio_governance_attestation_registry import ReleasePortfolioGovernanceAttestationRegistryStore, registry_summary
from song_agent.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry
from song_agent.release_portfolio_governance_attestation_verifier import verify_release_portfolio_governance_attestation
from song_agent.releases import stable_hash


PORTAL_SCHEMA_VERSION = 1
PORTAL_PACKAGE_TYPE = "release_portfolio_governance_attestation_portal"
PORTAL_REPORT_PACKAGE_TYPE = "release_portfolio_governance_attestation_portal_report"
PORTAL_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}
PORTAL_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}
PORTAL_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}
PORTAL_PAGES = ("index.html", "current.html", "registry.html", "revocations.html", "verify.html")


class ReleasePortfolioGovernanceAttestationPortalError(ValueError):
    pass


class ReleasePortfolioGovernanceAttestationPortalNotFoundError(ReleasePortfolioGovernanceAttestationPortalError):
    pass


class ReleasePortfolioGovernanceAttestationPortalStateError(ReleasePortfolioGovernanceAttestationPortalError):
    pass


class ReleasePortfolioGovernanceAttestationPortalStore:
    def __init__(
        self,
        *,
        registry_store: ReleasePortfolioGovernanceAttestationRegistryStore,
        attestation_store: ReleasePortfolioGovernanceAttestationStore,
    ) -> None:
        self.registry_store = registry_store
        self.attestation_store = attestation_store
        self.lock = threading.RLock()

    def root_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        root = self.attestation_store.portfolio_store.portfolio_dir(portfolio_id) / "governance-attestation-portal"
        if profile == "public_summary":
            return root
        return root / "profiles" / _safe_profile(profile)

    def report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "portal-report.json"

    def history_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "portal-history.jsonl"

    def verification_report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "portal-verification-report.json"

    def export_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "export"

    def zip_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "governance-attestation-portal.zip"

    def read_report(self, portfolio_id: str, *, profile: str = "public_summary", default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(portfolio_id, profile), default=default)

    def read_export_manifest(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        path = self.export_dir(portfolio_id, profile) / "portal-manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceAttestationPortalNotFoundError("Attestation Portal export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTAL_BLOCKED_KEYS)

    def refresh_report(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            self.attestation_store.portfolio_store.get_portfolio(portfolio_id)
            source = self.build_source(portfolio_id, profile=profile)
            blockers, warnings, checks = self._findings(source)
            summary = _portal_summary_from_source(source, blockers, warnings)
            report = {
                "schema_version": PORTAL_SCHEMA_VERSION,
                "package_type": PORTAL_REPORT_PACKAGE_TYPE,
                "portfolio_id": portfolio_id,
                "attestation_profile": profile,
                "generated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "readiness": "blocked" if blockers else "portal_ready",
                "source": source,
                "summary": summary,
                "blockers": blockers,
                "warnings": warnings,
                "checks": checks,
                "source_hash": stable_hash(source),
            }
            report["integrity_hash"] = portal_report_hash(report)
            self.root_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(portfolio_id, profile), report)
            self._append_history(portfolio_id, profile, "portal_report_refreshed", {"status": report["status"], "source_hash": report["source_hash"]}, now=now)
            return sanitize_metadata(report, blocked_keys=PORTAL_BLOCKED_KEYS)

    def build_source(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        registry_zip = self.registry_store.zip_path(portfolio_id, profile)
        registry_verification = verify_release_portfolio_governance_attestation_registry(registry_zip, strict=True, require_current=True, require_published=True, require_no_revoked_current=True)
        registry_manifest = _read_zip_json(registry_zip, "portal-manifest.json") or _read_zip_json(registry_zip, "manifest.json")
        registry = _read_zip_json(registry_zip, "registry.json")
        current_id = str(registry.get("current_entry_id") or "")
        current = _find_entry(registry, current_id) if current_id else {}
        current_source = current.get("source") if isinstance(current.get("source"), dict) else {}
        attestation_zip = self.attestation_store.zip_path(portfolio_id, profile)
        attestation_verification = verify_release_portfolio_governance_attestation(attestation_zip, strict=True, require_vault=True, require_final_board=True)
        attestation_manifest = _read_zip_json(attestation_zip, "manifest.json")
        registry_counts = registry_summary(registry)
        source = {
            "portfolio_id": portfolio_id,
            "attestation_profile": profile,
            "registry_zip_sha256": _sha256(registry_zip),
            "registry_zip_size_bytes": registry_zip.stat().st_size if registry_zip.exists() and registry_zip.is_file() else None,
            "registry_manifest_hash": registry_manifest.get("integrity_hash") if registry_manifest else registry_verification.get("manifest_hash"),
            "registry_verification_hash": _verification_hash(registry_verification) if registry_verification else None,
            "registry_verification_status": registry_verification.get("status") if registry_verification else "missing",
            "registry_current_entry_id": current_id or None,
            "registry_current_entry_hash": current.get("integrity_hash") if current else None,
            "registry_current_entry_status": current.get("status") if current else "missing",
            "current_certificate_id": current.get("certificate_id") if current else None,
            "current_attestation_zip_sha256": current_source.get("attestation_zip_sha256") if current else None,
            "current_attestation_zip_size_bytes": current_source.get("attestation_zip_size_bytes") if current else None,
            "current_attestation_manifest_hash": current_source.get("attestation_manifest_hash") if current else None,
            "current_attestation_verification_hash": current_source.get("attestation_verification_hash") if current else None,
            "current_attestation_verification_status": current_source.get("attestation_verification_status") if current else "missing",
            "attestation_zip_sha256": attestation_verification.get("zip_sha256"),
            "attestation_manifest_hash": attestation_manifest.get("integrity_hash") if attestation_manifest else attestation_verification.get("manifest_hash"),
            "attestation_verification_hash": _verification_hash(attestation_verification) if attestation_verification else None,
            "attestation_verification_status": attestation_verification.get("status") if attestation_verification else "missing",
            "evidence_vault_zip_sha256": current_source.get("evidence_vault_zip_sha256") if current else None,
            "evidence_vault_manifest_hash": current_source.get("evidence_vault_manifest_hash") if current else None,
            "evidence_vault_verification_hash": current_source.get("evidence_vault_verification_hash") if current else None,
            "evidence_vault_deep_verification_status": current_source.get("evidence_vault_deep_verification_status") if current else "missing",
            "final_board_signoff_hash": current_source.get("final_board_signoff_hash") if current else None,
            "published_count": registry_counts.get("published_count", 0),
            "revoked_count": registry_counts.get("revoked_count", 0),
            "superseded_count": registry_counts.get("superseded_count", 0),
        }
        return sanitize_metadata(source, blocked_keys=PORTAL_BLOCKED_KEYS)

    def report_is_stale(self, portfolio_id: str, report: dict[str, Any] | None = None, *, profile: str = "public_summary") -> bool:
        data = report if isinstance(report, dict) else self.read_report(portfolio_id, profile=profile, default={})
        if not data:
            return False
        try:
            source = self.build_source(portfolio_id, profile=str((data.get("source") if isinstance(data.get("source"), dict) else {}).get("attestation_profile") or profile))
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_portal(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            report = self.read_report(portfolio_id, profile=profile, default={}) or self.refresh_report(portfolio_id, {"profile": profile}, now=now)
            source = self.build_source(portfolio_id, profile=profile)
            self._ensure_exportable(report, source)
            external_review = _accepted_evidence_summary_for_portfolio_dir(self.attestation_store.portfolio_store.portfolio_dir(portfolio_id), profile=profile)
            external_review_verification = _accepted_evidence_verification_summary_for_portfolio_dir(self.attestation_store.portfolio_store.portfolio_dir(portfolio_id), profile=profile)
            state = {**_state_triple(report), "external_review_hash": stable_hash(external_review), "external_review_verification_hash": stable_hash(external_review_verification)}
            if self._history_has_state_event(portfolio_id, profile, state, "portal_exported"):
                raise ReleasePortfolioGovernanceAttestationPortalStateError("Attestation Portal export already exists for this source state.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            existing_manifest = _read_json_default(export_dir / "portal-manifest.json", default={})
            if _manifest_state(existing_manifest) == state:
                raise ReleasePortfolioGovernanceAttestationPortalStateError("Attestation Portal export already exists for this source state.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "data").mkdir(parents=True, exist_ok=True)

            _write_json(export_dir / "portal-report.json", report)
            data_docs = _data_documents(report)
            data_docs["accepted-evidence-summary.json"] = {"source_hash": report.get("source_hash"), "external_review": external_review}
            data_docs["accepted-evidence-verification-summary.json"] = {"source_hash": report.get("source_hash"), "accepted_evidence_verification": external_review_verification}
            for name, payload_doc in data_docs.items():
                _write_json(export_dir / "data" / name, payload_doc)
            for name, content in _html_pages(report, data_docs, external_review=external_review).items():
                (export_dir / name).write_text(content, encoding="utf-8")
            _write_readme(export_dir, report)

            pages = [_page_record(export_dir, name, report.get("source_hash")) for name in PORTAL_PAGES]
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "portal-manifest.json"]
            manifest = {
                "schema_version": PORTAL_SCHEMA_VERSION,
                "package_type": PORTAL_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Release Portfolio Governance Attestation Portal", "version": __version__},
                "portfolio_id": portfolio_id,
                "attestation_profile": profile,
                "created_at": now,
                "source_hash": report.get("source_hash"),
                "portal_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "registry": _registry_manifest_row(source),
                "current_attestation": _attestation_manifest_row(source),
                "external_review": external_review,
                "external_review_verification": external_review_verification,
                "pages": pages,
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"report": report, "data": data_docs}),
            }
            manifest["integrity_hash"] = portal_manifest_hash(manifest)
            _write_json(export_dir / "portal-manifest.json", manifest)
            self._append_history(portfolio_id, profile, "portal_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=PORTAL_BLOCKED_KEYS)

    def build_zip(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            report = self.read_report(portfolio_id, profile=profile, default={})
            source = self.build_source(portfolio_id, profile=profile)
            self._ensure_exportable(report, source)
            external_review = _accepted_evidence_summary_for_portfolio_dir(self.attestation_store.portfolio_store.portfolio_dir(portfolio_id), profile=profile)
            external_review_verification = _accepted_evidence_verification_summary_for_portfolio_dir(self.attestation_store.portfolio_store.portfolio_dir(portfolio_id), profile=profile)
            state = {**_state_triple(report), "external_review_hash": stable_hash(external_review), "external_review_verification_hash": stable_hash(external_review_verification)}
            if self._history_has_state_event(portfolio_id, profile, state, "portal_zip_built"):
                raise ReleasePortfolioGovernanceAttestationPortalStateError("Attestation Portal ZIP already exists for this source state.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            zip_path = self.zip_path(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "portal-manifest.json").exists():
                if self._history_has_state_event(portfolio_id, profile, state, "portal_exported"):
                    raise ReleasePortfolioGovernanceAttestationPortalStateError("Attestation Portal export already exists for this source state.")
                self.export_portal(portfolio_id, {"profile": profile}, now=now)
            if zip_path.exists():
                manifest_in_zip = _read_zip_json(zip_path, "portal-manifest.json")
                if _manifest_state(manifest_in_zip) == state:
                    raise ReleasePortfolioGovernanceAttestationPortalStateError("Attestation Portal ZIP already exists for this source state.")
            manifest = read_json(export_dir / "portal-manifest.json")
            if stable_hash(manifest.get("external_review") if isinstance(manifest.get("external_review"), dict) else {}) != stable_hash(external_review):
                raise ReleasePortfolioGovernanceAttestationPortalStateError("Attestation Portal export is stale. Re-export before ZIP.")
            if stable_hash(manifest.get("external_review_verification") if isinstance(manifest.get("external_review_verification"), dict) else {}) != stable_hash(external_review_verification):
                raise ReleasePortfolioGovernanceAttestationPortalStateError("Attestation Portal accepted evidence verification is stale. Re-export before ZIP.")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = portal_manifest_hash(manifest)
            _write_json(export_dir / "portal-manifest.json", manifest)
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
            self._append_history(portfolio_id, profile, "portal_zip_built", {**state, "sha256": info["sha256"]}, now=now)
            return sanitize_metadata(info, blocked_keys=PORTAL_BLOCKED_KEYS)

    def summary(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        report = self.read_report(portfolio_id, profile=profile, default={})
        verification = _read_json_default(self.verification_report_path(portfolio_id, profile), default={})
        summary = portal_summary(report) if report else {"status": "missing", "profile": profile}
        summary["verification_status"] = verification.get("status") or "missing"
        return sanitize_metadata(summary, blocked_keys=PORTAL_BLOCKED_KEYS)

    def _findings(self, source: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []

        def check(check_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            row = {"check_id": check_id, "status": "passed" if passed else "warning" if warning else "failed", "severity": "warning" if warning else "blocking", "message": message}
            checks.append(row)
            if not passed:
                (warnings if warning else blockers).append({"check_id": check_id, "severity": row["severity"], "message": message})

        check("registry_verification_passed", source.get("registry_verification_status") == "passed", "Attestation Registry ZIP verification is passed.")
        check("current_entry_published", source.get("registry_current_entry_status") == "published", "Registry current entry is published.")
        check("attestation_verification_passed", source.get("attestation_verification_status") == "passed", "Current Public Attestation ZIP verification is passed.")
        check("current_attestation_zip_matches", bool(source.get("current_attestation_zip_sha256")) and source.get("current_attestation_zip_sha256") == source.get("attestation_zip_sha256"), "Current entry attestation ZIP hash matches the current Public Attestation ZIP.")
        check("current_attestation_manifest_matches", bool(source.get("current_attestation_manifest_hash")) and source.get("current_attestation_manifest_hash") == source.get("attestation_manifest_hash"), "Current entry attestation manifest hash matches current Public Attestation manifest.")
        check("evidence_vault_fingerprint_present", bool(source.get("evidence_vault_zip_sha256") and source.get("evidence_vault_manifest_hash") and source.get("evidence_vault_verification_hash")), "Evidence Vault public fingerprints are present.")
        check("final_board_signoff_present", bool(source.get("final_board_signoff_hash")), "Final Board signoff hash is present.")
        check("redaction_scan", _redaction_summary(source).get("status") == "passed", "Portal source contains no sensitive values.")
        return blockers, warnings, checks

    def _ensure_exportable(self, report: dict[str, Any], source: dict[str, Any]) -> None:
        if not portal_report_integrity_ok(report):
            raise ReleasePortfolioGovernanceAttestationPortalStateError("Attestation Portal Report integrity failed.")
        if report.get("status") == "failed":
            raise ReleasePortfolioGovernanceAttestationPortalStateError("Attestation Portal Report is failed. Refresh source evidence before export.")
        if report.get("source_hash") != stable_hash(source):
            raise ReleasePortfolioGovernanceAttestationPortalStateError("Attestation Portal Report is stale. Refresh before export.")

    def _append_history(self, portfolio_id: str, profile: str, event_type: str, summary: dict[str, Any], *, now: str) -> None:
        path = self.history_path(portfolio_id, profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"portal-event-{count + 1:06d}", "at": now, "type": event_type, "summary": summary}, blocked_keys=PORTAL_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _history_has_state_event(self, portfolio_id: str, profile: str, state: dict[str, str], event_type: str) -> bool:
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
            if all(str(summary.get(key) or "") == str(value or "") for key, value in state.items()):
                return True
        return False


def portal_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in PORTAL_REPORT_HASH_EXCLUDE_KEYS})


def portal_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == portal_report_hash(data)


def portal_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in PORTAL_MANIFEST_HASH_EXCLUDE_KEYS})


def portal_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == portal_manifest_hash(data)


def portal_summary(report: dict[str, Any]) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "readiness": data.get("readiness") or "missing",
            "portfolio_id": data.get("portfolio_id"),
            "current_entry_id": summary.get("current_entry_id"),
            "current_certificate_id": summary.get("current_certificate_id"),
            "registry_status": summary.get("registry_status"),
            "attestation_status": summary.get("attestation_status"),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=PORTAL_BLOCKED_KEYS,
    )


def portal_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata({"status": report.get("status"), "portfolio_id": summary.get("portfolio_id"), "current_entry_id": summary.get("current_entry_id"), "blocker_count": summary.get("blocker_count", 0), "warning_count": summary.get("warning_count", 0), "zip_sha256": report.get("zip_sha256"), "manifest_hash": report.get("manifest_hash")}, blocked_keys=PORTAL_BLOCKED_KEYS)


def _portal_summary_from_source(source: dict[str, Any], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "portfolio_id": source.get("portfolio_id"),
            "current_certificate_id": source.get("current_certificate_id"),
            "current_entry_id": source.get("registry_current_entry_id"),
            "registry_status": source.get("registry_verification_status"),
            "attestation_status": source.get("attestation_verification_status"),
            "portal_page_count": len(PORTAL_PAGES),
            "published_count": source.get("published_count", 0),
            "revoked_count": source.get("revoked_count", 0),
            "superseded_count": source.get("superseded_count", 0),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        blocked_keys=PORTAL_BLOCKED_KEYS,
    )


def _data_documents(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "portal-summary.json": {"source_hash": report.get("source_hash"), "summary": summary},
        "registry-summary.json": {
            "source_hash": report.get("source_hash"),
            "current_entry_id": source.get("registry_current_entry_id"),
            "current_certificate_id": source.get("current_certificate_id"),
            "published_count": source.get("published_count", 0),
            "revoked_count": source.get("revoked_count", 0),
            "superseded_count": source.get("superseded_count", 0),
            "registry_verification_status": source.get("registry_verification_status"),
            "registry_zip_sha256": source.get("registry_zip_sha256"),
            "registry_manifest_hash": source.get("registry_manifest_hash"),
            "registry_verification_hash": source.get("registry_verification_hash"),
            "current_entry_hash": source.get("registry_current_entry_hash"),
        },
        "current-attestation-summary.json": {
            "source_hash": report.get("source_hash"),
            "certificate_id": source.get("current_certificate_id"),
            "entry_id": source.get("registry_current_entry_id"),
            "attestation_zip_sha256": source.get("current_attestation_zip_sha256"),
            "attestation_manifest_hash": source.get("current_attestation_manifest_hash"),
            "attestation_verification_hash": source.get("current_attestation_verification_hash"),
            "attestation_verification_status": source.get("attestation_verification_status"),
            "evidence_vault_zip_sha256": source.get("evidence_vault_zip_sha256"),
            "evidence_vault_manifest_hash": source.get("evidence_vault_manifest_hash"),
            "evidence_vault_verification_hash": source.get("evidence_vault_verification_hash"),
            "evidence_vault_deep_verification_status": source.get("evidence_vault_deep_verification_status"),
            "final_board_signoff_hash": source.get("final_board_signoff_hash"),
        },
        "registry-verification-summary.json": {
            "source_hash": report.get("source_hash"),
            "status": source.get("registry_verification_status"),
            "zip_sha256": source.get("registry_zip_sha256"),
            "zip_size_bytes": source.get("registry_zip_size_bytes"),
            "manifest_hash": source.get("registry_manifest_hash"),
            "verification_hash": source.get("registry_verification_hash"),
            "current_entry_id": source.get("registry_current_entry_id"),
            "current_entry_hash": source.get("registry_current_entry_hash"),
            "current_entry_status": source.get("registry_current_entry_status"),
            "current_certificate_id": source.get("current_certificate_id"),
            "published_count": source.get("published_count", 0),
            "revoked_count": source.get("revoked_count", 0),
            "superseded_count": source.get("superseded_count", 0),
        },
        "attestation-verification-summary.json": {
            "source_hash": report.get("source_hash"),
            "status": source.get("attestation_verification_status"),
            "zip_sha256": source.get("current_attestation_zip_sha256"),
            "zip_size_bytes": source.get("current_attestation_zip_size_bytes"),
            "manifest_hash": source.get("current_attestation_manifest_hash"),
            "verification_hash": source.get("current_attestation_verification_hash"),
            "live_zip_sha256": source.get("attestation_zip_sha256"),
            "live_manifest_hash": source.get("attestation_manifest_hash"),
            "live_verification_hash": source.get("attestation_verification_hash"),
            "live_verification_status": source.get("attestation_verification_status"),
            "certificate_id": source.get("current_certificate_id"),
            "entry_id": source.get("registry_current_entry_id"),
            "evidence_vault_zip_sha256": source.get("evidence_vault_zip_sha256"),
            "evidence_vault_manifest_hash": source.get("evidence_vault_manifest_hash"),
            "evidence_vault_verification_hash": source.get("evidence_vault_verification_hash"),
            "evidence_vault_deep_verification_status": source.get("evidence_vault_deep_verification_status"),
            "final_board_signoff_hash": source.get("final_board_signoff_hash"),
        },
        "verification-commands.json": {
            "source_hash": report.get("source_hash"),
            "portal": "python -m song_agent.cli verify-release-portfolio-governance-attestation-portal governance-attestation-portal.zip --strict --require-current --json",
            "registry": "python -m song_agent.cli verify-release-portfolio-governance-attestation-registry governance-attestation-registry.zip --strict --require-current --require-published --json",
            "attestation": "python -m song_agent.cli verify-release-portfolio-governance-attestation governance-attestation.zip --strict --require-vault --require-final-board --json",
            "note": "Portal ZIP contains summaries only. Full deep audit requires the Evidence Vault ZIP.",
        },
    }


def _html_pages(report: dict[str, Any], data_docs: dict[str, dict[str, Any]], *, external_review: dict[str, Any] | None = None) -> dict[str, str]:
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    external = external_review if isinstance(external_review, dict) else {}
    base = _html_shell
    hashes = {
        "Registry ZIP": source.get("registry_zip_sha256"),
        "Current Attestation ZIP": source.get("current_attestation_zip_sha256"),
        "Evidence Vault ZIP": source.get("evidence_vault_zip_sha256"),
        "Final Board Signoff": source.get("final_board_signoff_hash"),
    }
    index_body = [
        "<h1>MusicForge Release Portfolio Governance Public Attestation Portal</h1>",
        _kv("Portfolio ID", source.get("portfolio_id")),
        _kv("Current certificate", source.get("current_certificate_id")),
        _kv("Current entry", source.get("registry_current_entry_id")),
        _kv("Registry status", source.get("registry_verification_status")),
        _kv("Attestation status", source.get("attestation_verification_status")),
        _kv("External Review", _external_review_label(external)),
        _kv("Published / revoked / superseded", f"{source.get('published_count', 0)} / {source.get('revoked_count', 0)} / {source.get('superseded_count', 0)}"),
        _hash_table(hashes),
        _links(),
    ]
    current_body = [
        "<h1>Current Public Attestation</h1>",
        _kv("Certificate ID", source.get("current_certificate_id")),
        _kv("Entry ID", source.get("registry_current_entry_id")),
        _kv("Attestation profile", source.get("attestation_profile")),
        _kv("Attestation verification", source.get("attestation_verification_status")),
        _kv("Evidence Vault deep verification", source.get("evidence_vault_deep_verification_status")),
        _kv("External Review", _external_review_label(external)),
        _kv("Final Board signoff hash", source.get("final_board_signoff_hash")),
        "<p>This page is a summary. Run verifier for evidence validation.</p>",
        _links(),
    ]
    registry_body = [
        "<h1>Registry Lifecycle Summary</h1>",
        _kv("Current entry", summary.get("current_entry_id")),
        _kv("Current certificate", summary.get("current_certificate_id")),
        _kv("Published count", summary.get("published_count")),
        _kv("Revoked count", summary.get("revoked_count")),
        _kv("Superseded count", summary.get("superseded_count")),
        _links(),
    ]
    revocations_body = [
        "<h1>Revocations and Supersedes</h1>",
        _kv("Revoked entries", source.get("revoked_count", 0)),
        _kv("Superseded entries", source.get("superseded_count", 0)),
        "<p>Detailed lifecycle evidence is available in the Attestation Registry package.</p>",
        _links(),
    ]
    verify_body = [
        "<h1>Offline Verification</h1>",
        "<pre>python -m song_agent.cli verify-release-portfolio-governance-attestation-portal governance-attestation-portal.zip --strict --require-current --json</pre>",
        "<p>This Portal ZIP contains summaries only. Full deep audit requires the Evidence Vault ZIP.</p>",
        '<p><a href="data/verification-commands.json">verification-commands.json</a></p>',
        _links(),
    ]
    pages = {
        "index.html": base("index.html", "Overview", "".join(index_body), report),
        "current.html": base("current.html", "Current", "".join(current_body), report),
        "registry.html": base("registry.html", "Registry", "".join(registry_body), report),
        "revocations.html": base("revocations.html", "Revocations", "".join(revocations_body), report),
        "verify.html": base("verify.html", "Verify", "".join(verify_body), report),
    }
    del data_docs
    return pages


def _html_shell(page: str, title: str, body: str, report: dict[str, Any]) -> str:
    source_hash = html.escape(str(report.get("source_hash") or ""))
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{html.escape(title)} - MusicForge Attestation Portal</title>\n"
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.45;color:#17202a;background:#fff}nav a{margin-right:1rem}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:.35rem .55rem}code,pre{background:#f4f4f4;padding:.2rem .35rem}</style>\n"
        "</head>\n"
        f'<body data-source-hash="{source_hash}" data-page="{html.escape(page)}">\n'
        f"<nav>{_links()}</nav>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def _links() -> str:
    return '<a href="index.html">Overview</a><a href="current.html">Current</a><a href="registry.html">Registry</a><a href="revocations.html">Revocations</a><a href="verify.html">Verify</a>'


def _kv(label: str, value: Any) -> str:
    return f"<p><strong>{html.escape(label)}:</strong> {html.escape(str(value if value is not None else 'missing'))}</p>"


def _hash_table(rows: dict[str, Any]) -> str:
    body = "".join(f"<tr><th>{html.escape(str(key))}</th><td><code>{html.escape(str(value or 'missing')[:16])}</code></td></tr>" for key, value in rows.items())
    return f"<table>{body}</table>"


def _external_review_label(external: dict[str, Any]) -> str:
    status = str(external.get("external_review_status") or external.get("status") or "missing")
    if status == "accepted":
        reviewer = str(external.get("reviewer_label") or "external reviewer")
        reviewed_at = str(external.get("reviewed_at") or "")
        return f"Accepted by {reviewer}" + (f" at {reviewed_at}" if reviewed_at else "")
    if status == "stale":
        return "Stale evidence"
    return status


def _registry_manifest_row(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "zip_sha256": source.get("registry_zip_sha256"),
        "zip_size_bytes": source.get("registry_zip_size_bytes"),
        "manifest_hash": source.get("registry_manifest_hash"),
        "verification_hash": source.get("registry_verification_hash"),
        "verification_status": source.get("registry_verification_status"),
        "current_entry_id": source.get("registry_current_entry_id"),
        "current_entry_hash": source.get("registry_current_entry_hash"),
    }


def _attestation_manifest_row(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "certificate_id": source.get("current_certificate_id"),
        "zip_sha256": source.get("current_attestation_zip_sha256"),
        "zip_size_bytes": source.get("current_attestation_zip_size_bytes"),
        "manifest_hash": source.get("current_attestation_manifest_hash"),
        "verification_hash": source.get("current_attestation_verification_hash"),
        "verification_status": source.get("attestation_verification_status"),
    }


def _state_triple(report: dict[str, Any]) -> dict[str, str]:
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    return {"source_hash": str(report.get("source_hash") or ""), "current_entry_hash": str(source.get("registry_current_entry_hash") or ""), "registry_zip_sha256": str(source.get("registry_zip_sha256") or "")}


def _manifest_state(manifest: dict[str, Any]) -> dict[str, str]:
    registry = manifest.get("registry") if isinstance(manifest.get("registry"), dict) else {}
    external = manifest.get("external_review") if isinstance(manifest.get("external_review"), dict) else {}
    external_verification = manifest.get("external_review_verification") if isinstance(manifest.get("external_review_verification"), dict) else {}
    return {"source_hash": str(manifest.get("source_hash") or ""), "current_entry_hash": str(registry.get("current_entry_hash") or ""), "registry_zip_sha256": str(registry.get("zip_sha256") or ""), "external_review_hash": stable_hash(external), "external_review_verification_hash": stable_hash(external_verification)}


def _page_record(root: Path, path: str, source_hash: Any) -> dict[str, Any]:
    resolved = root / path
    return {"path": path, "content_hash": _sha256(resolved), "source_hash": source_hash}


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]


def _read_json_default(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return value if isinstance(value, dict) else dict(default or {})


def _read_zip_json(zip_path: Path, entry: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, sanitize_metadata(payload, blocked_keys=PORTAL_BLOCKED_KEYS))


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
        raise ReleasePortfolioGovernanceAttestationPortalStateError("Resolved path escapes Attestation Portal directory.") from exc


def _redaction_summary(value: Any) -> dict[str, Any]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}


def _write_readme(export_dir: Path, report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    (export_dir / "README.txt").write_text(
        "\n".join(
            [
                "MusicForge Release Portfolio Governance Attestation Portal Snapshot",
                "",
                f"Portfolio ID: {report.get('portfolio_id')}",
                f"Current entry: {summary.get('current_entry_id') or 'none'}",
                f"Current certificate: {summary.get('current_certificate_id') or 'none'}",
                "This static portal is offline and does not publish anything to the internet.",
                "Run verify-release-portfolio-governance-attestation-portal before relying on it.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _accepted_evidence_summary_for_portfolio_dir(portfolio_dir: Path, *, profile: str = "public_summary") -> dict[str, Any]:
    try:
        from song_agent.release_portfolio_governance_attestation_accepted_evidence import accepted_evidence_public_summary_from_portfolio_dir

        return accepted_evidence_public_summary_from_portfolio_dir(portfolio_dir, profile=profile)
    except Exception:
        return {"status": "missing", "external_review_status": "missing"}


def _accepted_evidence_verification_summary_for_portfolio_dir(portfolio_dir: Path, *, profile: str = "public_summary") -> dict[str, Any]:
    try:
        from song_agent.release_portfolio_governance_attestation_accepted_evidence import accepted_evidence_verification_summary_from_portfolio_dir

        return accepted_evidence_verification_summary_from_portfolio_dir(portfolio_dir, profile=profile)
    except Exception:
        return {
            "package_type": "release_portfolio_governance_attestation_accepted_evidence_verification_summary",
            "profile": profile,
            "accepted_evidence_status": "missing",
            "external_review_status": "missing",
            "accepted_evidence_verification_status": "missing",
        }


def _find_entry(registry: dict[str, Any], entry_id: str) -> dict[str, Any]:
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == entry_id:
            return entry
    return {}


def _safe_profile(profile: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(profile or "public_summary"))[:80]


def _verification_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "generated_at"})
