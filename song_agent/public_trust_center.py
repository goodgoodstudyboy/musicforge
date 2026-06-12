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
from song_agent.release_portfolio_governance_attestation_accepted_evidence import accepted_evidence_verification_summary_from_portfolio_dir
from song_agent.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal
from song_agent.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry
from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore, verification_hash as ack_verification_hash
from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import verify_release_portfolio_governance_attestation_transparency_acknowledgement_package
from song_agent.release_portfolio_governance_attestation_transparency_verifier import verify_release_portfolio_governance_attestation_transparency
from song_agent.releases import ReleaseStore, stable_hash


PTC_SCHEMA_VERSION = 1
PTC_PACKAGE_TYPE = "musicforge_public_trust_center"
PTC_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_report"
PTC_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}
PTC_CONFIG_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
PTC_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}
PTC_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}
PTC_HTML_PAGES = ("index.html", "releases.html", "portfolios.html", "evidence.html", "risk.html", "verify.html")


class PublicTrustCenterError(ValueError):
    pass


class PublicTrustCenterNotFoundError(PublicTrustCenterError):
    pass


class PublicTrustCenterStateError(PublicTrustCenterError):
    pass


class PublicTrustCenterStore:
    def __init__(
        self,
        *,
        release_store: ReleaseStore,
        portfolio_store: Any,
        registry_store: Any,
        portal_store: Any,
        transparency_store: Any,
        acknowledgement_store: ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore,
    ) -> None:
        self.release_store = release_store
        self.portfolio_store = portfolio_store
        self.registry_store = registry_store
        self.portal_store = portal_store
        self.transparency_store = transparency_store
        self.acknowledgement_store = acknowledgement_store
        self.root = release_store.root.parent / "public-trust-centers"
        self.lock = threading.RLock()

    def center_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root / _safe_id(center_id or "ptc-default")

    def config_path(self, center_id: str = "ptc-default") -> Path:
        return self.center_dir(center_id) / "trust-center.json"

    def report_path(self, center_id: str = "ptc-default") -> Path:
        return self.center_dir(center_id) / "trust-center-report.json"

    def export_dir(self, center_id: str = "ptc-default") -> Path:
        return self.center_dir(center_id) / "export"

    def zip_path(self, center_id: str = "ptc-default") -> Path:
        return self.center_dir(center_id) / "public-trust-center.zip"

    def verification_report_path(self, center_id: str = "ptc-default") -> Path:
        return self.center_dir(center_id) / "public-trust-center-verification-report.json"

    def history_path(self, center_id: str = "ptc-default") -> Path:
        return self.center_dir(center_id) / "trust-center-history.jsonl"

    def list_centers(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(self.root.iterdir()):
            if not path.is_dir():
                continue
            config = _read_json_default(path / "trust-center.json", default={})
            report = _read_json_default(path / "trust-center-report.json", default={})
            if config:
                rows.append({"center": public_trust_center_config_summary(config), "summary": public_trust_center_summary(report) if report else {"status": "missing"}})
        return rows

    def read_config(self, center_id: str = "ptc-default", *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.config_path(center_id), default=default)

    def read_report(self, center_id: str = "ptc-default", *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(center_id), default=default)

    def read_export_manifest(self, center_id: str = "ptc-default") -> dict[str, Any]:
        path = self.export_dir(center_id) / "trust-center-manifest.json"
        if not path.exists():
            raise PublicTrustCenterNotFoundError("Public Trust Center export has not been generated.")
        value = read_json(path)
        return value if isinstance(value, dict) else {}

    def create_or_update_center(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            center_id = _safe_id(str(payload.get("center_id") or payload.get("id") or "ptc-default"))
            existing = self.read_config(center_id, default={})
            selection = _normalize_selection(payload.get("selection") if isinstance(payload.get("selection"), dict) else payload)
            policy = _normalize_policy(payload.get("policy") if isinstance(payload.get("policy"), dict) else payload)
            config = {
                "schema_version": PTC_SCHEMA_VERSION,
                "package_type": "musicforge_public_trust_center_config",
                "center_id": center_id,
                "name": str(payload.get("name") or existing.get("name") or "MusicForge Public Trust Center"),
                "created_at": existing.get("created_at") or now,
                "updated_at": now,
                "selection": selection,
                "policy": policy,
            }
            config["integrity_hash"] = public_trust_center_config_hash(config)
            self.center_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.config_path(center_id), config)
            self._append_history(center_id, "trust_center_config_saved", {"center_id": center_id, "config_hash": config["integrity_hash"]}, now=now)
            return _sanitize_public_metadata(config)

    def get_center(self, center_id: str = "ptc-default") -> dict[str, Any]:
        config = self.read_config(center_id, default={})
        if not config:
            raise PublicTrustCenterNotFoundError(f"Public Trust Center not found: {center_id}")
        report = self.read_report(center_id, default={})
        summary = public_trust_center_summary(report) if report else {"status": "missing", "center_id": center_id}
        if report:
            summary["stale"] = self.report_is_stale(center_id, report)
        return {"config": config, "report": report, "summary": summary}

    def build_source(self, center_id: str = "ptc-default") -> dict[str, Any]:
        config = self.read_config(center_id, default={}) or self.create_or_update_center({"center_id": center_id})
        selection = config.get("selection") if isinstance(config.get("selection"), dict) else {}
        profile = str(selection.get("attestation_profile") or "public_summary")
        releases = self._release_summaries(selection)
        portfolios = self._portfolio_summaries(selection, profile=profile)
        packages = [pkg for item in portfolios for pkg in item.get("public_packages", []) if isinstance(pkg, dict)]
        verifications = [ver for item in portfolios for ver in item.get("verification_summaries", []) if isinstance(ver, dict)]
        transparency = [item.get("transparency_summary", {}) for item in portfolios if isinstance(item.get("transparency_summary"), dict)]
        acknowledgements = [item.get("acknowledgement_summary", {}) for item in portfolios if isinstance(item.get("acknowledgement_summary"), dict)]
        source = {
            "center_id": center_id,
            "profile": profile,
            "config_hash": config.get("integrity_hash"),
            "selection": selection,
            "policy": config.get("policy") if isinstance(config.get("policy"), dict) else {},
            "release_count": len(releases),
            "portfolio_count": len(portfolios),
            "releases": releases,
            "portfolios": portfolios,
            "public_package_fingerprints": sorted(packages, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type")))),
            "verification_fingerprints": sorted(verifications, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type")))),
            "transparency": transparency,
            "acknowledgements": acknowledgements,
        }
        return _sanitize_public_metadata(source)

    def refresh_report(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            if payload:
                self.create_or_update_center({**payload, "center_id": center_id}, now=now)
            source = self.build_source(center_id)
            blockers, warnings, checks = _findings_from_source(source)
            summary = public_trust_center_summary_from_source(source, blockers, warnings)
            report = {
                "schema_version": PTC_SCHEMA_VERSION,
                "package_type": PTC_REPORT_PACKAGE_TYPE,
                "center_id": center_id,
                "generated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "readiness": "blocked" if blockers else "review_needed" if warnings else "public_trust_ready",
                "source": source,
                "source_hash": stable_hash(source),
                "summary": summary,
                "release_readiness": _release_readiness(source),
                "portfolio_readiness": _portfolio_readiness(source),
                "package_index": _package_index(source),
                "verification_index": _verification_index(source),
                "risk_register": _risk_register(source, blockers, warnings),
                "blockers": blockers,
                "warnings": warnings,
                "checks": checks,
            }
            report["integrity_hash"] = public_trust_center_report_hash(report)
            self.center_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(center_id), report)
            self._append_history(center_id, "trust_center_report_refreshed", {"status": report["status"], "source_hash": report["source_hash"]}, now=now)
            return _sanitize_public_metadata(report)

    def report_is_stale(self, center_id: str = "ptc-default", report: dict[str, Any] | None = None) -> bool:
        data = report if isinstance(report, dict) else self.read_report(center_id, default={})
        if not data:
            return False
        try:
            source = self.build_source(center_id)
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_center(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            report = self.read_report(center_id, default={}) or self.refresh_report(center_id, payload or {}, now=now)
            source = self.build_source(center_id)
            self._ensure_exportable(report, source)
            state = _state_row(report)
            if self._history_has_state_event(center_id, state, "trust_center_exported"):
                raise PublicTrustCenterStateError("Public Trust Center export already exists for this source state.")
            export_dir = self.export_dir(center_id).resolve()
            root = self.center_dir(center_id).resolve()
            _ensure_within(root, export_dir)
            existing_manifest = _read_json_default(export_dir / "trust-center-manifest.json", default={})
            if _manifest_state(existing_manifest) == state:
                raise PublicTrustCenterStateError("Public Trust Center export already exists for this source state.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "data").mkdir(parents=True, exist_ok=True)

            _write_json(export_dir / "trust-center-report.json", report)
            data_docs = public_trust_center_data_documents(report)
            for name, doc in data_docs.items():
                _write_json(export_dir / "data" / name, doc)
            pages = public_trust_center_html_pages(report, data_docs)
            for name, content in pages.items():
                (export_dir / name).write_text(content, encoding="utf-8")
            _write_readme(export_dir, report)

            page_rows = [_page_record(export_dir, name, report.get("source_hash")) for name in PTC_HTML_PAGES]
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "trust-center-manifest.json"]
            manifest = {
                "schema_version": PTC_SCHEMA_VERSION,
                "package_type": PTC_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center", "version": __version__},
                "center_id": center_id,
                "created_at": now,
                "source_hash": report.get("source_hash"),
                "trust_center_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "release_count": report.get("summary", {}).get("release_count"),
                "portfolio_count": report.get("summary", {}).get("portfolio_count"),
                "public_package_count": report.get("summary", {}).get("public_package_count"),
                "verification_count": report.get("summary", {}).get("verification_count"),
                "pages": page_rows,
                "data": {
                    "trust_center_data_hash": stable_hash(data_docs["trust-center-data.json"]),
                    "package_index_hash": stable_hash(data_docs["package-index.json"]),
                    "verification_index_hash": stable_hash(data_docs["verification-index.json"]),
                    "public_package_verification_index_hash": stable_hash(data_docs["public-package-verification-index.json"]),
                    "risk_register_hash": stable_hash(data_docs["risk-register.json"]),
                },
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
            }
            manifest["integrity_hash"] = public_trust_center_manifest_hash(manifest)
            _write_json(export_dir / "trust-center-manifest.json", manifest)
            self._append_history(center_id, "trust_center_exported", {"source_hash": report.get("source_hash"), "manifest_hash": manifest["integrity_hash"], **state}, now=now)
            return _sanitize_public_metadata(manifest)

    def build_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            del payload
            report = self.read_report(center_id, default={})
            if not report:
                raise PublicTrustCenterStateError("Public Trust Center report has not been generated.")
            source = self.build_source(center_id)
            self._ensure_exportable(report, source)
            state = _state_row(report)
            if self._history_has_state_event(center_id, state, "trust_center_zip_built"):
                raise PublicTrustCenterStateError("Public Trust Center ZIP already exists for this source state.")
            manifest = self.read_export_manifest(center_id)
            if _manifest_state(manifest) != state:
                raise PublicTrustCenterStateError("Public Trust Center export is stale. Rebuild export before ZIP.")
            export_dir = self.export_dir(center_id).resolve()
            zip_path = self.zip_path(center_id).resolve()
            _ensure_within(self.center_dir(center_id).resolve(), zip_path)
            if zip_path.exists():
                existing_state = _zip_manifest_state(zip_path)
                if existing_state == state:
                    raise PublicTrustCenterStateError("Public Trust Center ZIP already exists for this source state.")
                zip_path.unlink()
            _write_zip(zip_path, export_dir)
            zip_info = {"filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(_zip_entries(export_dir)), "created_at": now, "entries": [name for _path, name in _zip_entries(export_dir)]}
            manifest["zip"] = zip_info
            manifest["integrity_hash"] = public_trust_center_manifest_hash(manifest)
            _write_json(export_dir / "trust-center-manifest.json", manifest)
            zip_path.unlink()
            _write_zip(zip_path, export_dir)
            zip_info["sha256"] = _sha256(zip_path)
            zip_info["size_bytes"] = zip_path.stat().st_size
            self._append_history(center_id, "trust_center_zip_built", {"source_hash": report.get("source_hash"), "zip_sha256": zip_info["sha256"], "manifest_hash": manifest["integrity_hash"], **state}, now=now)
            return _sanitize_public_metadata(zip_info)

    def verify_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        from song_agent.public_trust_center_verifier import verify_public_trust_center_package, write_public_trust_center_verification_report

        payload = payload or {}
        report = verify_public_trust_center_package(
            self.zip_path(center_id),
            strict=bool(payload.get("strict", True)),
            require_registry_current=bool(payload.get("require_registry_current", False)),
            require_portal_current=bool(payload.get("require_portal_current", False)),
            require_transparency_current=bool(payload.get("require_transparency_current", False)),
            require_acknowledgement_current=bool(payload.get("require_acknowledgement_current", False)),
            now=now,
        )
        write_public_trust_center_verification_report(report, self.verification_report_path(center_id))
        self._append_history(center_id, "trust_center_zip_verified", {"status": report.get("status"), "zip_sha256": report.get("zip_sha256"), "manifest_hash": report.get("manifest_hash")}, now=now or now_iso())
        return report

    def archive_snapshot(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            reason = str((payload or {}).get("reason") or "public trust center snapshot archived")
            report = self.read_report(center_id, default={})
            manifest = self.read_export_manifest(center_id)
            zip_path = self.zip_path(center_id)
            if not zip_path.exists():
                raise PublicTrustCenterStateError("Public Trust Center ZIP has not been generated.")
            archive = {
                "schema_version": PTC_SCHEMA_VERSION,
                "center_id": center_id,
                "archived_at": now,
                "source_hash": report.get("source_hash"),
                "report_integrity_hash": report.get("integrity_hash"),
                "manifest_hash": manifest.get("integrity_hash"),
                "zip_sha256": _sha256(zip_path),
                "zip_size_bytes": zip_path.stat().st_size,
                "reason": reason,
            }
            archive["integrity_hash"] = stable_hash(archive)
            self._append_history(center_id, "trust_center_archived", archive, now=now)
            return _sanitize_public_metadata(archive)

    def _release_summaries(self, selection: dict[str, Any]) -> list[dict[str, Any]]:
        ids = [str(item).strip() for item in selection.get("release_ids", []) if str(item).strip()] if isinstance(selection.get("release_ids"), list) else []
        if not ids and bool(selection.get("include_all_releases", True)):
            try:
                ids = [item.release_id for item in self.release_store.list_releases(include_hidden=False)]
            except Exception:
                ids = []
        rows: list[dict[str, Any]] = []
        for release_id in sorted(dict.fromkeys(ids)):
            try:
                release = self.release_store.get_release(release_id)
                signoff = self.release_store.read_signoff(release_id, default={})
                export_manifest = _read_json_default(self.release_store.export_dir(release_id) / "manifest.json", default={})
                rows.append(
                    {
                        "release_id": release.release_id,
                        "name": release.name,
                        "release_type": release.release_type,
                        "status": release.status,
                        "track_count": len(release.tracks),
                        "signoff_status": signoff.get("status") or signoff.get("summary", {}).get("status") or "missing",
                        "signoff_hash": signoff.get("integrity_hash") or signoff.get("payload_hash"),
                        "export_manifest_hash": export_manifest.get("integrity_hash"),
                        "zip_sha256": _sha256(self.release_store.zip_path(release_id)),
                    }
                )
            except Exception as exc:
                rows.append({"release_id": release_id, "status": "missing", "error": str(exc)})
        return rows

    def _portfolio_summaries(self, selection: dict[str, Any], *, profile: str) -> list[dict[str, Any]]:
        ids = [str(item).strip() for item in selection.get("portfolio_ids", []) if str(item).strip()] if isinstance(selection.get("portfolio_ids"), list) else []
        if not ids and bool(selection.get("include_all_portfolios", True)):
            try:
                ids = [str(item.get("portfolio_id")) for item in self.portfolio_store.list_portfolios(include_archived=False) if item.get("portfolio_id")]
            except Exception:
                ids = []
        rows: list[dict[str, Any]] = []
        for portfolio_id in sorted(dict.fromkeys(ids)):
            rows.append(self._portfolio_summary(portfolio_id, profile=profile))
        return rows

    def _portfolio_summary(self, portfolio_id: str, *, profile: str) -> dict[str, Any]:
        portfolio = {}
        try:
            portfolio = self.portfolio_store.get_portfolio(portfolio_id)
        except Exception:
            portfolio = {"portfolio_id": portfolio_id, "status": "missing"}
        registry = self._package_summary("registry", portfolio_id, profile, self.registry_store.zip_path(portfolio_id, profile), "trust-center-registry", lambda path: verify_release_portfolio_governance_attestation_registry(path, strict=True, require_current=True, require_published=True, require_no_revoked_current=True), self.registry_store.export_dir(portfolio_id, profile) / "manifest.json")
        portal = self._package_summary("portal", portfolio_id, profile, self.portal_store.zip_path(portfolio_id, profile), "trust-center-portal", lambda path: verify_release_portfolio_governance_attestation_portal(path, strict=True, require_current=True, require_registry=True, require_attestation=True, require_accepted_evidence=False), self.portal_store.export_dir(portfolio_id, profile) / "portal-manifest.json")
        transparency = self._package_summary("transparency", portfolio_id, profile, self.transparency_store.zip_path(portfolio_id, profile), "trust-center-transparency", lambda path: verify_release_portfolio_governance_attestation_transparency(path, strict=True, require_current=True, require_accepted_evidence=True, require_contiguous_chain=True), self.transparency_store.export_dir(portfolio_id, profile) / "transparency-manifest.json")
        ack = self._package_summary("transparency_acknowledgement", portfolio_id, profile, self.acknowledgement_store.evidence_zip_path(portfolio_id, profile), "trust-center-acknowledgement", lambda path: verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(path, strict=True, require_response=True, require_accepted=True), self.acknowledgement_store.evidence_export_dir(portfolio_id, profile) / "acknowledgement-evidence-manifest.json")
        public_packages = [registry["package"], portal["package"], transparency["package"], ack["package"]]
        verification_summaries = [registry["verification"], portal["verification"], transparency["verification"], ack["verification"]]
        accepted_verification = accepted_evidence_verification_summary_from_portfolio_dir(self._portfolio_dir(portfolio_id), profile=profile)
        return sanitize_metadata(
            {
                "portfolio_id": portfolio_id,
                "name": portfolio.get("name") or portfolio.get("title") or portfolio_id,
                "status": portfolio.get("status") or "active",
                "profile": profile,
                "public_package_status": _aggregate_status([item.get("verification_status") for item in public_packages]),
                "public_packages": public_packages,
                "verification_summaries": verification_summaries,
                "registry_summary": registry["summary"],
                "portal_summary": portal["summary"],
                "transparency_summary": transparency["summary"],
                "acknowledgement_summary": ack["summary"],
                "accepted_evidence_verification": accepted_verification,
            },
            blocked_keys=PTC_BLOCKED_KEYS,
        )

    def _package_summary(self, package_type: str, portfolio_id: str, profile: str, zip_path: Path, check_prefix: str, verifier, manifest_path: Path) -> dict[str, Any]:
        manifest = _read_json_default(manifest_path, default={})
        summary: dict[str, Any] = {}
        verification: dict[str, Any] = {}
        if zip_path.exists():
            try:
                verification = verifier(zip_path)
            except Exception as exc:
                verification = {"status": "failed", "error": str(exc), "checks": [{"check_id": f"{check_prefix}-exception", "status": "failed", "message": str(exc)}]}
        else:
            verification = {"status": "missing", "checks": []}
        verification_hash = _verification_hash(verification)
        package = {
            "portfolio_id": portfolio_id,
            "profile": profile,
            "package_type": package_type,
            "zip_sha256": _sha256(zip_path),
            "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() and zip_path.is_file() else None,
            "manifest_hash": manifest.get("integrity_hash") or verification.get("manifest_hash"),
            "verification_hash": verification_hash,
            "verification_status": verification.get("status") or "missing",
        }
        if isinstance(verification.get("summary"), dict):
            summary = dict(verification["summary"])
        return {"package": package, "verification": {**package, "blocker_count": len(verification.get("blockers", []) if isinstance(verification.get("blockers"), list) else [])}, "summary": summary}

    def _portfolio_dir(self, portfolio_id: str) -> Path:
        if hasattr(self.portfolio_store, "portfolio_dir"):
            return self.portfolio_store.portfolio_dir(portfolio_id)
        candidate = getattr(self.registry_store, "attestation_store", None)
        candidate = getattr(candidate, "portfolio_store", None)
        if candidate is not None and hasattr(candidate, "portfolio_dir"):
            return candidate.portfolio_dir(portfolio_id)
        candidate = getattr(self.transparency_store, "attestation_store", None)
        candidate = getattr(candidate, "portfolio_store", None)
        if candidate is not None and hasattr(candidate, "portfolio_dir"):
            return candidate.portfolio_dir(portfolio_id)
        raise PublicTrustCenterStateError("Public Trust Center cannot resolve portfolio evidence directory.")

    def _ensure_exportable(self, report: dict[str, Any], source: dict[str, Any]) -> None:
        if not report:
            raise PublicTrustCenterStateError("Public Trust Center report has not been generated.")
        if str(report.get("source_hash") or "") != stable_hash(source):
            raise PublicTrustCenterStateError("Public Trust Center source is stale. Refresh before export.")
        if not public_trust_center_report_integrity_ok(report):
            raise PublicTrustCenterStateError("Public Trust Center report integrity failed.")

    def _append_history(self, center_id: str, event_type: str, payload: dict[str, Any], *, now: str | None = None) -> None:
        path = self.history_path(center_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event_type": event_type, "created_at": now or now_iso(), "payload": sanitize_metadata(payload, blocked_keys=PTC_BLOCKED_KEYS)}, ensure_ascii=False, sort_keys=True) + "\n")

    def _history_has_state_event(self, center_id: str, state: dict[str, Any], event_type: str) -> bool:
        path = self.history_path(center_id)
        if not path.exists():
            return False
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event_type") != event_type:
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if all(str(payload.get(key) or "") == str(value or "") for key, value in state.items()):
                return True
        return False


def public_trust_center_config_hash(config: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in config.items() if key not in PTC_CONFIG_HASH_EXCLUDE_KEYS})


def public_trust_center_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in report.items() if key not in PTC_REPORT_HASH_EXCLUDE_KEYS})


def public_trust_center_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key not in PTC_MANIFEST_HASH_EXCLUDE_KEYS})


def public_trust_center_report_integrity_ok(report: dict[str, Any]) -> bool:
    return bool(report) and str(report.get("integrity_hash") or "") == public_trust_center_report_hash(report)


def public_trust_center_manifest_integrity_ok(manifest: dict[str, Any]) -> bool:
    return bool(manifest) and str(manifest.get("integrity_hash") or "") == public_trust_center_manifest_hash(manifest)


def public_trust_center_config_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {"center_id": config.get("center_id"), "name": config.get("name"), "updated_at": config.get("updated_at"), "integrity_ok": str(config.get("integrity_hash") or "") == public_trust_center_config_hash(config)}


def public_trust_center_summary(report: dict[str, Any]) -> dict[str, Any]:
    if not report:
        return {"status": "missing"}
    summary = dict(report.get("summary") if isinstance(report.get("summary"), dict) else {})
    summary.update({"center_id": report.get("center_id"), "status": report.get("status"), "readiness": report.get("readiness"), "source_hash": report.get("source_hash"), "integrity_ok": public_trust_center_report_integrity_ok(report)})
    return summary


def public_trust_center_summary_from_source(source: dict[str, Any], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    package_count = len(source.get("public_package_fingerprints", []) if isinstance(source.get("public_package_fingerprints"), list) else [])
    verification_count = len(source.get("verification_fingerprints", []) if isinstance(source.get("verification_fingerprints"), list) else [])
    passed_verifications = sum(1 for item in source.get("verification_fingerprints", []) if isinstance(item, dict) and item.get("verification_status") == "passed")
    return {
        "center_id": source.get("center_id"),
        "profile": source.get("profile"),
        "release_count": int(source.get("release_count") or 0),
        "portfolio_count": int(source.get("portfolio_count") or 0),
        "public_package_count": package_count,
        "verification_count": verification_count,
        "passed_verification_count": passed_verifications,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "readiness": "blocked" if blockers else "review_needed" if warnings else "public_trust_ready",
    }


def public_trust_center_data_documents(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    source_hash = report.get("source_hash")
    release_index = {"source_hash": source_hash, "releases": report.get("release_readiness", [])}
    portfolio_index = {"source_hash": source_hash, "portfolios": report.get("portfolio_readiness", [])}
    package_index = {"source_hash": source_hash, "packages": report.get("package_index", [])}
    verification_index = {"source_hash": source_hash, "verifications": report.get("verification_index", [])}
    risk_register = {"source_hash": source_hash, "risks": report.get("risk_register", [])}
    transparency_index = {"source_hash": source_hash, "transparency": source.get("transparency", [])}
    acknowledgement_index = {"source_hash": source_hash, "acknowledgements": source.get("acknowledgements", [])}
    verification_sidecar = {
        "source_hash": source_hash,
        "packages": _package_verification_sidecars(source),
        "verifications": _verification_sidecars(source),
    }
    data = {
        "source_hash": source_hash,
        "summary": report.get("summary", {}),
        "releases": release_index["releases"],
        "portfolios": portfolio_index["portfolios"],
        "packages": package_index["packages"],
        "verifications": verification_index["verifications"],
        "package_verification_summaries": verification_sidecar["packages"],
        "risks": risk_register["risks"],
        "transparency": transparency_index["transparency"],
        "acknowledgements": acknowledgement_index["acknowledgements"],
    }
    return {
        "trust-center-data.json": data,
        "release-index.json": release_index,
        "portfolio-index.json": portfolio_index,
        "package-index.json": package_index,
        "verification-index.json": verification_index,
        "public-package-verification-index.json": verification_sidecar,
        "risk-register.json": risk_register,
        "transparency-index.json": transparency_index,
        "acknowledgement-index.json": acknowledgement_index,
    }


def public_trust_center_html_pages(report: dict[str, Any], data_docs: dict[str, dict[str, Any]]) -> dict[str, str]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    source_hash = str(report.get("source_hash") or "")
    report_hash = str(report.get("integrity_hash") or "")
    data_hash = stable_hash(data_docs.get("trust-center-data.json", {}))
    package_rows = data_docs.get("package-index.json", {}).get("packages", []) if isinstance(data_docs.get("package-index.json"), dict) else []
    risk_rows = data_docs.get("risk-register.json", {}).get("risks", []) if isinstance(data_docs.get("risk-register.json"), dict) else []
    body = {
        "index.html": [
            "<h1>MusicForge Public Trust Center</h1>",
            _kv("Status", summary.get("status")),
            _kv("Readiness", summary.get("readiness")),
            _kv("Releases", summary.get("release_count")),
            _kv("Portfolios", summary.get("portfolio_count")),
            _kv("Public packages", summary.get("public_package_count")),
            _kv("Passed verifications", summary.get("passed_verification_count")),
            _links(),
        ],
        "releases.html": [
            "<h1>Release Readiness</h1>",
            _table(data_docs.get("release-index.json", {}).get("releases", []) if isinstance(data_docs.get("release-index.json"), dict) else [], ("release_id", "name", "status", "signoff_status")),
            _links(),
        ],
        "portfolios.html": [
            "<h1>Portfolio Governance</h1>",
            _table(data_docs.get("portfolio-index.json", {}).get("portfolios", []) if isinstance(data_docs.get("portfolio-index.json"), dict) else [], ("portfolio_id", "status", "public_package_status")),
            _links(),
        ],
        "evidence.html": [
            "<h1>Public Evidence Fingerprints</h1>",
            _table(package_rows, ("portfolio_id", "package_type", "verification_status", "zip_sha256", "manifest_hash")),
            _links(),
        ],
        "risk.html": [
            "<h1>Public Risk Register</h1>",
            _table(risk_rows, ("risk_id", "severity", "category", "title")),
            _links(),
        ],
        "verify.html": [
            "<h1>Offline Verification</h1>",
            "<pre>python -m song_agent.cli verify-public-trust-center-package public-trust-center.zip --strict --json</pre>",
            "<p>This Trust Center references evidence packages by fingerprint and does not embed internal ZIP files.</p>",
            _links(),
        ],
    }
    return {name: _html_shell(name, title=name, body="".join(parts), source_hash=source_hash, report_hash=report_hash, data_hash=data_hash) for name, parts in body.items()}


def expected_public_trust_center_documents(report: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    data_docs = public_trust_center_data_documents(report)
    return data_docs, public_trust_center_html_pages(report, data_docs)


def _normalize_selection(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "release_ids": [str(item).strip() for item in payload.get("release_ids", []) if str(item).strip()] if isinstance(payload.get("release_ids"), list) else [],
        "portfolio_ids": [str(item).strip() for item in payload.get("portfolio_ids", []) if str(item).strip()] if isinstance(payload.get("portfolio_ids"), list) else [],
        "include_all_releases": bool(payload.get("include_all_releases", True)),
        "include_all_portfolios": bool(payload.get("include_all_portfolios", True)),
        "attestation_profile": str(payload.get("attestation_profile") or payload.get("profile") or "public_summary"),
    }


def _normalize_policy(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "require_registry_current": bool(payload.get("require_registry_current", True)),
        "require_portal_current": bool(payload.get("require_portal_current", True)),
        "require_transparency_current": bool(payload.get("require_transparency_current", True)),
        "require_acknowledgement_current": bool(payload.get("require_acknowledgement_current", False)),
    }


def _findings_from_source(source: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    policy = source.get("policy") if isinstance(source.get("policy"), dict) else {}
    packages = source.get("public_package_fingerprints", []) if isinstance(source.get("public_package_fingerprints"), list) else []
    portfolio_count = int(source.get("portfolio_count") or 0)
    if portfolio_count == 0:
        warnings.append(_finding("no_portfolios", "warning", "No Portfolio Governance public evidence is selected."))
    required = {
        "registry": bool(policy.get("require_registry_current", True)),
        "portal": bool(policy.get("require_portal_current", True)),
        "transparency": bool(policy.get("require_transparency_current", True)),
        "transparency_acknowledgement": bool(policy.get("require_acknowledgement_current", False)),
    }
    for package_type, enabled in required.items():
        if not enabled:
            continue
        matching = [item for item in packages if isinstance(item, dict) and item.get("package_type") == package_type]
        if portfolio_count and len(matching) < portfolio_count:
            blockers.append(_finding(f"{package_type}_missing", "critical", f"{package_type} evidence is missing for one or more portfolios."))
        failed = [item for item in matching if item.get("verification_status") != "passed"]
        if failed:
            blockers.append(_finding(f"{package_type}_verification_failed", "critical", f"{package_type} verification is not passed."))
    for package_type in sorted(required):
        matching = [item for item in packages if isinstance(item, dict) and item.get("package_type") == package_type]
        ok = (not required[package_type]) or (len(matching) >= portfolio_count and all(item.get("verification_status") == "passed" for item in matching))
        checks.append({"check_id": f"ptc_{package_type}_coverage", "status": "passed" if ok else "failed", "severity": "blocking", "message": f"{package_type} coverage {'passed' if ok else 'failed'}."})
    checks.append({"check_id": "ptc_source_redaction", "status": "passed" if _redaction_summary(source)["status"] == "passed" else "failed", "severity": "blocking", "message": "Public Trust Center source redaction scan completed."})
    if _redaction_summary(source)["status"] != "passed":
        blockers.append(_finding("source_redaction", "critical", "Public Trust Center source contains sensitive values."))
    return blockers, warnings, checks


def _release_readiness(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in source.get("releases", []) if isinstance(source.get("releases"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "release_id": item.get("release_id"),
                "name": item.get("name"),
                "status": item.get("status"),
                "signoff_status": item.get("signoff_status"),
                "track_count": item.get("track_count", 0),
                "readiness": "ready" if item.get("signoff_status") in {"signed", "force_signed"} else "review_needed",
                "zip_sha256": item.get("zip_sha256"),
            }
        )
    return sorted(rows, key=lambda item: str(item.get("release_id") or ""))


def _portfolio_readiness(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in source.get("portfolios", []) if isinstance(source.get("portfolios"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append({"portfolio_id": item.get("portfolio_id"), "status": item.get("status"), "profile": item.get("profile"), "public_package_status": item.get("public_package_status")})
    return sorted(rows, key=lambda item: str(item.get("portfolio_id") or ""))


def _package_index(source: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted([dict(item) for item in source.get("public_package_fingerprints", []) if isinstance(item, dict)], key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _verification_index(source: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted([dict(item) for item in source.get("verification_fingerprints", []) if isinstance(item, dict)], key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _package_verification_sidecars(source: dict[str, Any]) -> list[dict[str, Any]]:
    packages = _package_index(source)
    verifications = {
        _fingerprint_key(item): dict(item)
        for item in source.get("verification_fingerprints", [])
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for package in packages:
        verification = verifications.get(_fingerprint_key(package), {})
        rows.append(
            {
                "portfolio_id": package.get("portfolio_id"),
                "profile": package.get("profile"),
                "package_type": package.get("package_type"),
                "zip_sha256": package.get("zip_sha256"),
                "zip_size_bytes": package.get("zip_size_bytes"),
                "manifest_hash": package.get("manifest_hash"),
                "verification_hash": package.get("verification_hash"),
                "verification_status": package.get("verification_status"),
                "verification_report_hash": verification.get("verification_hash") or package.get("verification_hash"),
                "verification_report_status": verification.get("verification_status") or package.get("verification_status"),
                "blocker_count": verification.get("blocker_count", 0),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _verification_sidecars(source: dict[str, Any]) -> list[dict[str, Any]]:
    packages = {
        _fingerprint_key(item): dict(item)
        for item in source.get("public_package_fingerprints", [])
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for verification in _verification_index(source):
        package = packages.get(_fingerprint_key(verification), {})
        rows.append(
            {
                "portfolio_id": verification.get("portfolio_id"),
                "profile": verification.get("profile"),
                "package_type": verification.get("package_type"),
                "verification_hash": verification.get("verification_hash"),
                "verification_status": verification.get("verification_status"),
                "blocker_count": verification.get("blocker_count", 0),
                "zip_sha256": package.get("zip_sha256") or verification.get("zip_sha256"),
                "zip_size_bytes": package.get("zip_size_bytes") or verification.get("zip_size_bytes"),
                "manifest_hash": package.get("manifest_hash") or verification.get("manifest_hash"),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _fingerprint_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("portfolio_id") or ""), str(item.get("package_type") or ""), str(item.get("profile") or ""))


def _risk_register(source: dict[str, Any], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for index, item in enumerate(blockers, start=1):
        risks.append({"risk_id": f"ptc-risk_{index:03d}", "severity": "critical", "category": item.get("check_id"), "title": item.get("message"), "source": "blocker"})
    offset = len(risks)
    for index, item in enumerate(warnings, start=1):
        risks.append({"risk_id": f"ptc-risk_{offset + index:03d}", "severity": "warning", "category": item.get("check_id"), "title": item.get("message"), "source": "warning"})
    if not risks and int(source.get("portfolio_count") or 0) > 0:
        risks.append({"risk_id": "ptc-risk_000", "severity": "info", "category": "ready", "title": "Public trust evidence is current.", "source": "system"})
    return risks


def _finding(check_id: str, severity: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": severity, "message": message}


def _aggregate_status(statuses: list[Any]) -> str:
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


def _state_row(report: dict[str, Any]) -> dict[str, str]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {"source_hash": str(report.get("source_hash") or ""), "report_integrity_hash": str(report.get("integrity_hash") or ""), "public_package_count": str(summary.get("public_package_count") or 0)}


def _manifest_state(manifest: dict[str, Any]) -> dict[str, str]:
    return {"source_hash": str(manifest.get("source_hash") or ""), "report_integrity_hash": str((manifest.get("trust_center_report") if isinstance(manifest.get("trust_center_report"), dict) else {}).get("integrity_hash") or ""), "public_package_count": str(manifest.get("public_package_count") or 0)}


def _zip_manifest_state(zip_path: Path) -> dict[str, str]:
    manifest = _read_zip_json(zip_path, "trust-center-manifest.json")
    return _manifest_state(manifest)


def _html_shell(page: str, title: str, body: str, *, source_hash: str, report_hash: str, data_hash: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{html.escape(title)} - MusicForge Public Trust Center</title>\n"
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.45;color:#17202a;background:#fff}nav a{margin-right:1rem}table{border-collapse:collapse;max-width:100%}td,th{border:1px solid #bbb;padding:.35rem .55rem;text-align:left}code,pre{background:#f4f4f4;padding:.2rem .35rem}</style>\n"
        "</head>\n"
        f'<body data-source-hash="{html.escape(source_hash)}" data-report-integrity="{html.escape(report_hash)}" data-data-hash="{html.escape(data_hash)}" data-page="{html.escape(page)}">\n'
        f"<nav>{_links()}</nav>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def _links() -> str:
    return '<a href="index.html">Overview</a><a href="releases.html">Releases</a><a href="portfolios.html">Portfolios</a><a href="evidence.html">Evidence</a><a href="risk.html">Risk</a><a href="verify.html">Verify</a>'


def _kv(label: str, value: Any) -> str:
    return f"<p><strong>{html.escape(label)}:</strong> {html.escape(str(value if value is not None else 'missing'))}</p>"


def _table(rows: Any, columns: tuple[str, ...]) -> str:
    if not isinstance(rows, list) or not rows:
        return "<p>No rows.</p>"
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = ""
    for row in rows[:250]:
        if not isinstance(row, dict):
            continue
        body += "<tr>" + "".join(f"<td>{html.escape(str(row.get(column, ''))[:96])}</td>" for column in columns) + "</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _page_record(root: Path, path: str, source_hash: Any) -> dict[str, Any]:
    resolved = root / path
    return {"path": path, "content_hash": _sha256(resolved), "source_hash": source_hash}


def _file_record(root: Path, path: Path) -> dict[str, Any]:
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
    return write_json(path, _sanitize_public_metadata(payload))


def _sanitize_public_metadata(value: Any, *, key: str = "") -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for child_key, child in value.items():
            text_key = str(child_key)
            if text_key.lower() in PTC_BLOCKED_KEYS:
                continue
            cleaned[text_key] = _sanitize_public_metadata(child, key=text_key)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_public_metadata(item, key=key) for item in value]
    if isinstance(value, str):
        text = "".join(char for char in value if char == "\n" or char == "\t" or ord(char) >= 32)
        if key in {"path", "filename", "entries"}:
            return text
        return sanitize_sensitive_text(text)
    return value


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verification_hash(report: dict[str, Any]) -> str | None:
    if not report:
        return None
    if report.get("schema_version") and "checks" in report:
        return ack_verification_hash(report)
    return stable_hash({key: value for key, value in report.items() if key != "generated_at"})


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise PublicTrustCenterStateError("Resolved path escapes Public Trust Center directory.") from exc


def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "ptc-default")).strip("-_")
    if not text:
        text = "ptc-default"
    return text[:80]


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
                "MusicForge Public Trust Center",
                "",
                f"Center ID: {report.get('center_id')}",
                f"Status: {summary.get('status')}",
                f"Readiness: {summary.get('readiness')}",
                "This package is offline and references public evidence packages by fingerprint only.",
                "Run verify-public-trust-center-package before relying on it.",
                "",
            ]
        ),
        encoding="utf-8",
    )
