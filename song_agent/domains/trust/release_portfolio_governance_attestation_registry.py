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
from song_agent.domains.trust.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore
from song_agent.domains.trust.release_portfolio_governance_attestation_verifier import verify_release_portfolio_governance_attestation
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_contracts import ENTRY_STATUSES, REGISTRY_BLOCKED_KEYS, REGISTRY_ENTRY_HASH_EXCLUDE_KEYS, REGISTRY_HASH_EXCLUDE_KEYS, REGISTRY_MANIFEST_HASH_EXCLUDE_KEYS, REGISTRY_PACKAGE_TYPE, REGISTRY_REPORT_HASH_EXCLUDE_KEYS, _find_entry, registry_entry_hash, registry_hash, registry_manifest_hash, registry_report_hash, registry_summary, registry_verification_summary


REGISTRY_SCHEMA_VERSION = 1

REGISTRY_REPORT_PACKAGE_TYPE = "release_portfolio_governance_attestation_registry_report"








class ReleasePortfolioGovernanceAttestationRegistryError(ValueError):
    pass


class ReleasePortfolioGovernanceAttestationRegistryNotFoundError(ReleasePortfolioGovernanceAttestationRegistryError):
    pass


class ReleasePortfolioGovernanceAttestationRegistryStateError(ReleasePortfolioGovernanceAttestationRegistryError):
    pass


class ReleasePortfolioGovernanceAttestationRegistryStore:
    def __init__(self, *, attestation_store: ReleasePortfolioGovernanceAttestationStore) -> None:
        self.attestation_store = attestation_store
        self.lock = threading.RLock()

    def root_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        root = self.attestation_store.portfolio_store.portfolio_dir(portfolio_id) / "governance-attestation-registry"
        if str(profile or "public_summary") == "public_summary":
            return root
        return root / "profiles" / str(profile)

    def registry_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "registry.json"

    def report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "registry-report.json"

    def history_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "registry-history.jsonl"

    def export_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "export"

    def zip_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "governance-attestation-registry.zip"

    def verification_report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "registry-verification-report.json"

    def read_registry(self, portfolio_id: str, *, profile: str = "public_summary", default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.registry_path(portfolio_id, profile), default=default)

    def read_report(self, portfolio_id: str, *, profile: str = "public_summary", default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(portfolio_id, profile), default=default)

    def get_entry(self, portfolio_id: str, entry_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        registry = self.read_registry(portfolio_id, profile=profile, default={})
        for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
            if isinstance(entry, dict) and entry.get("entry_id") == entry_id:
                return entry
        raise ReleasePortfolioGovernanceAttestationRegistryNotFoundError("Public Attestation Registry entry not found.")

    def register_current_attestation(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            self.attestation_store.portfolio_store.get_portfolio(portfolio_id)
            zip_path = self.attestation_store.zip_path(portfolio_id, profile)
            verification = verify_release_portfolio_governance_attestation(zip_path, strict=True, require_vault=True, require_final_board=True)
            if verification.get("status") != "passed":
                raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation ZIP verification failed. Refresh and verify attestation before registration.")
            manifest = _read_zip_json(zip_path, "manifest.json")
            certificate = _read_zip_json(zip_path, "certificate.json")
            report = _read_zip_json(zip_path, "attestation-report.json")
            source = _entry_source(zip_path, manifest, certificate, report, verification)
            registry = self._registry_or_empty(portfolio_id, profile, now=now)
            for entry in registry.get("entries", []):
                if isinstance(entry, dict) and entry.get("source", {}).get("attestation_zip_sha256") == source.get("attestation_zip_sha256"):
                    entry["existing"] = True
                    return sanitize_metadata({"existing": True, "entry": entry, "registry": registry}, blocked_keys=REGISTRY_BLOCKED_KEYS)
            entry = {
                "entry_id": self._reserve_entry_id(registry),
                "certificate_id": certificate.get("certificate_id"),
                "attestation_profile": profile,
                "status": "draft",
                "created_at": now,
                "published_at": None,
                "revoked_at": None,
                "revocation_reason": None,
                "superseded_by_entry_id": None,
                "source": source,
                "public": {
                    "title": sanitize_sensitive_text(str(payload.get("title") or "MusicForge Governance Public Attestation"))[:200],
                    "summary": sanitize_sensitive_text(str(payload.get("summary") or "Portfolio governance attestation is current and deep verified."))[:1000],
                    "public_url": sanitize_sensitive_text(str(payload.get("public_url") or "").strip())[:500] or None,
                    "distribution_note": sanitize_sensitive_text(str(payload.get("distribution_note") or "").strip())[:1000] or None,
                },
                "verification": {
                    "status": verification.get("status"),
                    "blocker_count": int((verification.get("summary") if isinstance(verification.get("summary"), dict) else {}).get("blocker_count") or 0),
                    "warning_count": int((verification.get("summary") if isinstance(verification.get("summary"), dict) else {}).get("warning_count") or 0),
                    "verified_at": verification.get("generated_at") or now,
                },
            }
            entry["integrity_hash"] = registry_entry_hash(entry)
            registry.setdefault("entries", []).append(entry)
            self._finalize_registry(registry, now=now)
            self._write_registry(portfolio_id, profile, registry)
            self._append_history(portfolio_id, profile, "entry_registered", {"entry_id": entry["entry_id"], "attestation_zip_sha256": source.get("attestation_zip_sha256")}, now=now)
            return sanitize_metadata({"existing": False, "entry": entry, "registry": registry}, blocked_keys=REGISTRY_BLOCKED_KEYS)

    def publish_entry(self, portfolio_id: str, entry_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            registry = self._require_registry(portfolio_id, profile)
            entry = _find_entry_mut(registry, entry_id)
            if entry.get("status") == "revoked":
                raise ReleasePortfolioGovernanceAttestationRegistryStateError("Revoked Public Attestation entries cannot be published.")
            if entry.get("status") not in {"draft", "published", "superseded"}:
                raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation entry status cannot be published.")
            self._ensure_entry_current(entry, profile=profile)
            current_id = registry.get("current_entry_id")
            if current_id and current_id != entry_id:
                if not bool(payload.get("supersede_current", False)):
                    raise ReleasePortfolioGovernanceAttestationRegistryStateError("A current published Public Attestation exists. Use supersede_current=true to replace it.")
                current = _find_entry_mut(registry, str(current_id))
                if current.get("status") == "published":
                    current["status"] = "superseded"
                    current["superseded_by_entry_id"] = entry_id
                    current["integrity_hash"] = registry_entry_hash(current)
            entry["status"] = "published"
            entry["published_at"] = entry.get("published_at") or now
            entry["revoked_at"] = None
            entry["revocation_reason"] = None
            if payload.get("public_url") is not None:
                entry.setdefault("public", {})["public_url"] = sanitize_sensitive_text(str(payload.get("public_url") or "").strip())[:500] or None
            if payload.get("distribution_note") is not None:
                entry.setdefault("public", {})["distribution_note"] = sanitize_sensitive_text(str(payload.get("distribution_note") or "").strip())[:1000] or None
            entry["integrity_hash"] = registry_entry_hash(entry)
            registry["current_entry_id"] = entry_id
            self._finalize_registry(registry, now=now)
            self._write_registry(portfolio_id, profile, registry)
            self._append_history(portfolio_id, profile, "entry_published", {"entry_id": entry_id, "superseded": current_id if current_id != entry_id else None, "published_by": _safe_text(payload.get("published_by"))}, now=now)
            return sanitize_metadata({"entry": entry, "registry": registry}, blocked_keys=REGISTRY_BLOCKED_KEYS)

    def revoke_entry(self, portfolio_id: str, entry_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise ReleasePortfolioGovernanceAttestationRegistryStateError("reason must be at least 8 characters.")
            registry = self._require_registry(portfolio_id, profile)
            entry = _find_entry_mut(registry, entry_id)
            if entry.get("status") not in {"published", "superseded"}:
                raise ReleasePortfolioGovernanceAttestationRegistryStateError("Only published or superseded Public Attestation entries can be revoked.")
            entry["status"] = "revoked"
            entry["revoked_at"] = now
            entry["revocation_reason"] = reason[:1000]
            entry["integrity_hash"] = registry_entry_hash(entry)
            if registry.get("current_entry_id") == entry_id:
                registry["current_entry_id"] = None
            self._finalize_registry(registry, now=now)
            self._write_registry(portfolio_id, profile, registry)
            self._append_history(portfolio_id, profile, "entry_revoked", {"entry_id": entry_id, "revoked_by": _safe_text(payload.get("revoked_by")), "reason_hash": stable_hash(reason)}, now=now)
            return sanitize_metadata({"entry": entry, "registry": registry}, blocked_keys=REGISTRY_BLOCKED_KEYS)

    def refresh_report(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            registry = self.read_registry(portfolio_id, profile=profile, default={}) or self._registry_or_empty(portfolio_id, profile, now=now)
            blockers, warnings, checks = self._findings(registry)
            summary = registry_summary(registry)
            current = _find_entry(registry, str(registry.get("current_entry_id") or "")) if registry.get("current_entry_id") else {}
            source = {
                "registry_hash": registry.get("integrity_hash"),
                "current_entry_id": registry.get("current_entry_id"),
                "current_entry_hash": current.get("integrity_hash") if current else None,
                "current_attestation_zip_sha256": (current.get("source") if isinstance(current.get("source"), dict) else {}).get("attestation_zip_sha256") if current else None,
                "current_attestation_manifest_hash": (current.get("source") if isinstance(current.get("source"), dict) else {}).get("attestation_manifest_hash") if current else None,
                "current_attestation_verification_hash": (current.get("source") if isinstance(current.get("source"), dict) else {}).get("attestation_verification_hash") if current else None,
                "evidence_vault_zip_sha256": (current.get("source") if isinstance(current.get("source"), dict) else {}).get("evidence_vault_zip_sha256") if current else None,
                "final_board_signoff_hash": (current.get("source") if isinstance(current.get("source"), dict) else {}).get("final_board_signoff_hash") if current else None,
            }
            report = {
                "schema_version": REGISTRY_SCHEMA_VERSION,
                "package_type": REGISTRY_REPORT_PACKAGE_TYPE,
                "portfolio_id": portfolio_id,
                "attestation_profile": profile,
                "generated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "summary": summary,
                "source": source,
                "findings": checks,
                "blockers": blockers,
                "warnings": warnings,
                "source_hash": stable_hash(source),
            }
            report["integrity_hash"] = registry_report_hash(report)
            self.root_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(portfolio_id, profile), report)
            self._append_history(portfolio_id, profile, "report_refreshed", {"status": report["status"], "source_hash": report["source_hash"]}, now=now)
            return sanitize_metadata(report, blocked_keys=REGISTRY_BLOCKED_KEYS)

    def export_registry(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            registry = self._require_registry(portfolio_id, profile)
            report = self.read_report(portfolio_id, profile=profile, default={}) or self.refresh_report(portfolio_id, {"profile": profile}, now=now)
            self._ensure_exportable(registry, report)
            external_review = _accepted_evidence_summary_for_portfolio_dir(self.attestation_store.portfolio_store.portfolio_dir(portfolio_id), profile=profile)
            external_review_verification = _accepted_evidence_verification_summary_for_portfolio_dir(self.attestation_store.portfolio_store.portfolio_dir(portfolio_id), profile=profile)
            state = {**_state_triple(registry), "external_review_hash": stable_hash(external_review), "external_review_verification_hash": stable_hash(external_review_verification)}
            if self._history_has_state_event(portfolio_id, profile, state, "registry_exported"):
                raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation Registry export already exists for this registry state.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            existing_manifest = _read_json_default(export_dir / "manifest.json", default={})
            if _manifest_state(existing_manifest) == state:
                raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation Registry export already exists for this registry state.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "data").mkdir(parents=True, exist_ok=True)
            package_index = build_package_index(registry, report, generated_at=now)
            chain = build_chain_of_custody(self.history_path(portfolio_id, profile), registry, report, generated_at=now)
            _write_json(export_dir / "registry.json", registry)
            _write_json(export_dir / "registry-report.json", report)
            _write_json(export_dir / "package-index.json", package_index)
            _write_json(export_dir / "chain-of-custody.json", chain)
            _write_json(export_dir / "data" / "accepted-evidence-summary.json", {"source_hash": report.get("source_hash"), "external_review": external_review})
            _write_json(export_dir / "data" / "accepted-evidence-verification-summary.json", {"source_hash": report.get("source_hash"), "accepted_evidence_verification": external_review_verification})
            _write_readme(export_dir, registry, report)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest = {
                "schema_version": REGISTRY_SCHEMA_VERSION,
                "package_type": REGISTRY_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Release Portfolio Governance Attestation Registry", "version": __version__},
                "portfolio_id": portfolio_id,
                "attestation_profile": profile,
                "created_at": now,
                "source_hash": report.get("source_hash"),
                "registry": {
                    "integrity_hash": registry.get("integrity_hash"),
                    "current_entry_id": registry.get("current_entry_id"),
                    "current_entry_hash": state.get("current_entry_hash"),
                },
                "registry_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "external_review": external_review,
                "external_review_verification": external_review_verification,
                "files": files,
                "zip": {},
            }
            manifest["integrity_hash"] = registry_manifest_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
            self._append_history(portfolio_id, profile, "registry_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=REGISTRY_BLOCKED_KEYS)

    def build_zip(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            registry = self._require_registry(portfolio_id, profile)
            report = self.read_report(portfolio_id, profile=profile, default={})
            self._ensure_exportable(registry, report)
            external_review = _accepted_evidence_summary_for_portfolio_dir(self.attestation_store.portfolio_store.portfolio_dir(portfolio_id), profile=profile)
            external_review_verification = _accepted_evidence_verification_summary_for_portfolio_dir(self.attestation_store.portfolio_store.portfolio_dir(portfolio_id), profile=profile)
            state = {**_state_triple(registry), "external_review_hash": stable_hash(external_review), "external_review_verification_hash": stable_hash(external_review_verification)}
            if self._history_has_state_event(portfolio_id, profile, state, "registry_zip_built"):
                raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation Registry ZIP already exists for this registry state.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            zip_path = self.zip_path(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "manifest.json").exists():
                if self._history_has_state_event(portfolio_id, profile, state, "registry_exported"):
                    raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation Registry export already exists for this registry state.")
                self.export_registry(portfolio_id, {"profile": profile}, now=now)
            if zip_path.exists():
                manifest_in_zip = _read_zip_json(zip_path, "manifest.json")
                if _manifest_state(manifest_in_zip) == state:
                    raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation Registry ZIP already exists for this registry state.")
            manifest = read_json(export_dir / "manifest.json")
            if stable_hash(manifest.get("external_review") if isinstance(manifest.get("external_review"), dict) else {}) != stable_hash(external_review):
                raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation Registry export is stale. Re-export before ZIP.")
            if stable_hash(manifest.get("external_review_verification") if isinstance(manifest.get("external_review_verification"), dict) else {}) != stable_hash(external_review_verification):
                raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation Registry accepted evidence verification is stale. Re-export before ZIP.")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = registry_manifest_hash(manifest)
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
            self._append_history(portfolio_id, profile, "registry_zip_built", {**state, "sha256": info["sha256"]}, now=now)
            return sanitize_metadata(info, blocked_keys=REGISTRY_BLOCKED_KEYS)

    def summary(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        registry = self.read_registry(portfolio_id, profile=profile, default={})
        report = self.read_report(portfolio_id, profile=profile, default={})
        verification = _read_json_default(self.verification_report_path(portfolio_id, profile), default={})
        summary = registry_summary(registry)
        summary["report_status"] = report.get("status") or "missing"
        summary["verification_status"] = verification.get("status") or "missing"
        return sanitize_metadata(summary, blocked_keys=REGISTRY_BLOCKED_KEYS)

    def _registry_or_empty(self, portfolio_id: str, profile: str, *, now: str) -> dict[str, Any]:
        registry = self.read_registry(portfolio_id, profile=profile, default={})
        if registry:
            return registry
        registry = {"schema_version": REGISTRY_SCHEMA_VERSION, "portfolio_id": portfolio_id, "attestation_profile": profile, "status": "empty", "current_entry_id": None, "entry_count": 0, "published_count": 0, "revoked_count": 0, "superseded_count": 0, "entries": [], "updated_at": now}
        registry["integrity_hash"] = registry_hash(registry)
        return registry

    def _require_registry(self, portfolio_id: str, profile: str) -> dict[str, Any]:
        registry = self.read_registry(portfolio_id, profile=profile, default={})
        if not registry:
            raise ReleasePortfolioGovernanceAttestationRegistryNotFoundError("Public Attestation Registry does not exist.")
        return registry

    def _write_registry(self, portfolio_id: str, profile: str, registry: dict[str, Any]) -> None:
        self.root_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
        _write_json(self.registry_path(portfolio_id, profile), sanitize_metadata(registry, blocked_keys=REGISTRY_BLOCKED_KEYS))

    def _finalize_registry(self, registry: dict[str, Any], *, now: str) -> None:
        entries = registry.get("entries") if isinstance(registry.get("entries"), list) else []
        registry["entry_count"] = len(entries)
        registry["published_count"] = sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "published")
        registry["revoked_count"] = sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "revoked")
        registry["superseded_count"] = sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "superseded")
        registry["status"] = "empty" if not entries else "active"
        registry["updated_at"] = now
        registry["integrity_hash"] = registry_hash(registry)

    def _findings(self, registry: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []

        def check(check_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            row = {"check_id": check_id, "status": "passed" if passed else "warning" if warning else "failed", "severity": "warning" if warning else "blocking", "message": message}
            checks.append(row)
            if passed:
                return
            (warnings if warning else blockers).append({"check_id": check_id, "severity": row["severity"], "message": message})

        entries = registry.get("entries") if isinstance(registry.get("entries"), list) else []
        check("registry_integrity", registry_integrity_ok(registry), "Registry integrity hash is valid.")
        ids = [str(item.get("entry_id") or "") for item in entries if isinstance(item, dict)]
        check("entry_ids_unique", len(ids) == len(set(ids)), "Registry entry IDs are unique.")
        for entry in entries:
            if not isinstance(entry, dict):
                check("entry_shape", False, "Registry entry must be an object.")
                continue
            check(f"{entry.get('entry_id')}_integrity", registry_entry_integrity_ok(entry), f"Entry {entry.get('entry_id')} integrity is valid.")
            check(f"{entry.get('entry_id')}_status", entry.get("status") in ENTRY_STATUSES, f"Entry {entry.get('entry_id')} status is valid.")
            if entry.get("status") == "superseded":
                target = str(entry.get("superseded_by_entry_id") or "")
                check(f"{entry.get('entry_id')}_superseded_target", bool(target) and target in ids, f"Superseded entry {entry.get('entry_id')} points to an existing replacement.")
        current_id = str(registry.get("current_entry_id") or "")
        current = _find_entry(registry, current_id) if current_id else {}
        check("current_entry_valid", not current_id or bool(current), "Current entry exists when set.")
        check("current_entry_published", not current_id or current.get("status") == "published", "Current entry is published.")
        if _redaction_summary(registry).get("status") == "failed":
            check("redaction_scan", False, "Registry contains sensitive values.")
        else:
            check("redaction_scan", True, "Registry contains no sensitive values.")
        return blockers, warnings, checks

    def _ensure_entry_current(self, entry: dict[str, Any], *, profile: str) -> None:
        zip_path = self.attestation_store.zip_path(str(entry.get("source", {}).get("portfolio_id") or ""), profile)
        # Fall back to digest-only evidence when the current attestation package has been moved.
        if zip_path.exists() and _sha256(zip_path) != entry.get("source", {}).get("attestation_zip_sha256"):
            raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation entry does not match the current attestation ZIP.")
        if entry.get("verification", {}).get("status") != "passed":
            raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation entry verification is not passed.")

    def _ensure_exportable(self, registry: dict[str, Any], report: dict[str, Any]) -> None:
        if not registry_integrity_ok(registry):
            raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation Registry integrity failed.")
        if not registry_report_integrity_ok(report):
            raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation Registry Report integrity failed.")
        source = report.get("source") if isinstance(report.get("source"), dict) else {}
        if source.get("registry_hash") != registry.get("integrity_hash") or report.get("source_hash") != stable_hash(source):
            raise ReleasePortfolioGovernanceAttestationRegistryStateError("Public Attestation Registry Report is stale. Refresh before export.")
        blockers, _warnings, _checks = self._findings(registry)
        if blockers or report.get("status") == "failed":
            detail = str((blockers[0] if blockers else {}).get("message") or "Registry Report is failed.")
            raise ReleasePortfolioGovernanceAttestationRegistryStateError(f"Public Attestation Registry cannot be exported: {detail}")

    def _reserve_entry_id(self, registry: dict[str, Any]) -> str:
        existing = {str(item.get("entry_id") or "") for item in registry.get("entries", []) if isinstance(item, dict)}
        index = len(existing) + 1
        while f"attreg-entry-{index:06d}" in existing:
            index += 1
        return f"attreg-entry-{index:06d}"

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

    def _append_history(self, portfolio_id: str, profile: str, event_type: str, summary: dict[str, Any], *, now: str) -> None:
        path = self.history_path(portfolio_id, profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"attreg-event-{count + 1:06d}", "at": now, "type": event_type, "summary": summary}, blocked_keys=REGISTRY_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")





def registry_integrity_ok(registry: dict[str, Any] | None) -> bool:
    data = registry if isinstance(registry, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == registry_hash(data)





def registry_entry_integrity_ok(entry: dict[str, Any] | None) -> bool:
    data = entry if isinstance(entry, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == registry_entry_hash(data)





def registry_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == registry_report_hash(data)





def registry_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == registry_manifest_hash(data)








def build_package_index(registry: dict[str, Any], report: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    entries = registry.get("entries") if isinstance(registry.get("entries"), list) else []
    items = [{"entry_id": item.get("entry_id"), "certificate_id": item.get("certificate_id"), "status": item.get("status"), **(item.get("source") if isinstance(item.get("source"), dict) else {})} for item in entries if isinstance(item, dict)]
    data = {"schema_version": REGISTRY_SCHEMA_VERSION, "portfolio_id": registry.get("portfolio_id"), "generated_at": generated_at, "source_hash": report.get("source_hash"), "summary": {"entry_count": len(items)}, "items": items}
    data["integrity_hash"] = stable_hash({key: value for key, value in data.items() if key != "integrity_hash"})
    return sanitize_metadata(data, blocked_keys=REGISTRY_BLOCKED_KEYS)


def build_chain_of_custody(history_path: Path, registry: dict[str, Any], report: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append({"event_id": event.get("event_id"), "at": event.get("at"), "type": event.get("type"), "summary_hash": stable_hash(event.get("summary") if isinstance(event.get("summary"), dict) else {})})
    data = {"schema_version": REGISTRY_SCHEMA_VERSION, "portfolio_id": registry.get("portfolio_id"), "generated_at": generated_at, "source_hash": report.get("source_hash"), "summary": {"event_count": len(events), "latest_event_type": events[-1].get("type") if events else None, "current_entry_id": registry.get("current_entry_id")}, "events": events}
    data["integrity_hash"] = stable_hash({key: value for key, value in data.items() if key != "integrity_hash"})
    return sanitize_metadata(data, blocked_keys=REGISTRY_BLOCKED_KEYS)


def _entry_source(zip_path: Path, manifest: dict[str, Any], certificate: dict[str, Any], report: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    evidence = manifest.get("evidence_vault") if isinstance(manifest.get("evidence_vault"), dict) else certificate.get("evidence_vault") if isinstance(certificate.get("evidence_vault"), dict) else {}
    return sanitize_metadata(
        {
            "portfolio_id": report.get("portfolio_id") or manifest.get("portfolio_id"),
            "attestation_zip_sha256": _sha256(zip_path),
            "attestation_zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
            "attestation_manifest_hash": manifest.get("integrity_hash"),
            "attestation_verification_hash": stable_hash(verification),
            "attestation_verification_status": verification.get("status"),
            "evidence_vault_zip_sha256": evidence.get("zip_sha256") or source.get("evidence_vault_zip_sha256"),
            "evidence_vault_zip_size_bytes": evidence.get("zip_size_bytes") or source.get("evidence_vault_zip_size_bytes"),
            "evidence_vault_manifest_hash": evidence.get("manifest_hash") or source.get("evidence_vault_manifest_hash"),
            "evidence_vault_verification_hash": evidence.get("verification_hash") or source.get("evidence_vault_verification_hash"),
            "evidence_vault_deep_verification_status": evidence.get("deep_verification_status") or source.get("evidence_vault_deep_verification_status"),
            "final_board_signoff_hash": source.get("final_board_signoff_hash") or (certificate.get("final_board") if isinstance(certificate.get("final_board"), dict) else {}).get("signoff_hash"),
        },
        blocked_keys=REGISTRY_BLOCKED_KEYS,
    )


def _state_triple(registry: dict[str, Any]) -> dict[str, str]:
    current = _find_entry(registry, str(registry.get("current_entry_id") or "")) if registry.get("current_entry_id") else {}
    return {"registry_hash": str(registry.get("integrity_hash") or ""), "current_entry_id": str(registry.get("current_entry_id") or ""), "current_entry_hash": str(current.get("integrity_hash") or "")}


def _manifest_state(manifest: dict[str, Any]) -> dict[str, str]:
    row = manifest.get("registry") if isinstance(manifest.get("registry"), dict) else {}
    external = manifest.get("external_review") if isinstance(manifest.get("external_review"), dict) else {}
    external_verification = manifest.get("external_review_verification") if isinstance(manifest.get("external_review_verification"), dict) else {}
    return {"registry_hash": str(row.get("integrity_hash") or ""), "current_entry_id": str(row.get("current_entry_id") or ""), "current_entry_hash": str(row.get("current_entry_hash") or ""), "external_review_hash": stable_hash(external), "external_review_verification_hash": stable_hash(external_verification)}





def _find_entry_mut(registry: dict[str, Any], entry_id: str) -> dict[str, Any]:
    entry = _find_entry(registry, entry_id)
    if not entry:
        raise ReleasePortfolioGovernanceAttestationRegistryNotFoundError("Public Attestation Registry entry not found.")
    return entry


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
    return write_json(path, sanitize_metadata(payload, blocked_keys=REGISTRY_BLOCKED_KEYS))


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
        raise ReleasePortfolioGovernanceAttestationRegistryStateError("Resolved path escapes Public Attestation Registry directory.") from exc


def _redaction_summary(value: Any) -> dict[str, Any]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}


def _write_readme(export_dir: Path, registry: dict[str, Any], report: dict[str, Any]) -> None:
    (export_dir / "README.txt").write_text(
        "\n".join(
            [
                "MusicForge Release Portfolio Governance Attestation Registry",
                "",
                f"Portfolio ID: {registry.get('portfolio_id')}",
                f"Current entry: {registry.get('current_entry_id') or 'none'}",
                f"Report status: {report.get('status')}",
                "This package records public attestation lifecycle metadata only.",
                "It does not contain Public Attestation ZIP or Evidence Vault ZIP files.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _accepted_evidence_summary_for_portfolio_dir(portfolio_dir: Path, *, profile: str = "public_summary") -> dict[str, Any]:
    try:
        from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model import accepted_evidence_public_summary_from_portfolio_dir

        return accepted_evidence_public_summary_from_portfolio_dir(portfolio_dir, profile=profile)
    except Exception:
        return {"status": "missing", "external_review_status": "missing"}


def _accepted_evidence_verification_summary_for_portfolio_dir(portfolio_dir: Path, *, profile: str = "public_summary") -> dict[str, Any]:
    try:
        from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model import accepted_evidence_verification_summary_from_portfolio_dir

        return accepted_evidence_verification_summary_from_portfolio_dir(portfolio_dir, profile=profile)
    except Exception:
        return {
            "package_type": "release_portfolio_governance_attestation_accepted_evidence_verification_summary",
            "profile": profile,
            "accepted_evidence_status": "missing",
            "external_review_status": "missing",
            "accepted_evidence_verification_status": "missing",
        }


def _safe_text(value: Any, limit: int = 160) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]
