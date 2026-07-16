from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import html
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
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model import accepted_evidence_verification_summary_from_portfolio_dir
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore, verification_hash as ack_verification_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import verify_release_portfolio_governance_attestation_transparency_acknowledgement_package
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_verifier import verify_release_portfolio_governance_attestation_transparency
from song_agent.domains.delivery.releases import ReleaseStore, stable_hash
from song_agent.domains.trust.public_trust_center_contracts import PTC_BLOCKED_KEYS, PTC_HTML_PAGES, PTC_MANIFEST_HASH_EXCLUDE_KEYS, PTC_PACKAGE_TYPE, PTC_REPORT_HASH_EXCLUDE_KEYS, _DELIVERY_COLLECTION_DOMAINS, _delivery_item_status, _delivery_public_payload, _delivery_summary_from_item, _delivery_summary_key, _delivery_verification_index_from_sidecars, _delivery_verification_index_from_source, _fingerprint_key, _html_shell, _kv, _links, _package_index, _package_verification_index_from_sidecars, _package_verification_sidecars, _table, _verification_index, _verification_sidecars, _verification_sidecars_from_docs, expected_public_trust_center_documents, public_trust_center_data_documents, public_trust_center_html_pages, public_trust_center_manifest_hash, public_trust_center_report_hash


PTC_SCHEMA_VERSION = 1

PTC_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_report"

PTC_CONFIG_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}



PTC_DELIVERY_DOMAINS = ("release", "distribution", "submission", "submission_evidence", "operations", "operations_audit", "operations_reviewer_pack")



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
        distribution_store: Any | None = None,
        submission_store: Any | None = None,
        submission_evidence_store: Any | None = None,
        operations_store: Any | None = None,
        operations_runbook_store: Any | None = None,
        operations_signoff_store: Any | None = None,
        operations_audit_store: Any | None = None,
        operations_reviewer_pack_store: Any | None = None,
    ) -> None:
        self.release_store = release_store
        self.portfolio_store = portfolio_store
        self.registry_store = registry_store
        self.portal_store = portal_store
        self.transparency_store = transparency_store
        self.acknowledgement_store = acknowledgement_store
        self.distribution_store = distribution_store
        self.submission_store = submission_store
        self.submission_evidence_store = submission_evidence_store
        self.operations_store = operations_store
        self.operations_runbook_store = operations_runbook_store
        self.operations_signoff_store = operations_signoff_store
        self.operations_audit_store = operations_audit_store
        self.operations_reviewer_pack_store = operations_reviewer_pack_store
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
        delivery = self._delivery_bundle(selection, releases, portfolios)
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
            **delivery,
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
                "delivery_readiness": _delivery_readiness(source),
                "package_index": _package_index(source),
                "verification_index": _verification_index(source),
                "risk_register": _risk_register(source, blockers, warnings),
                "delivery_risk_register": _delivery_risk_register(source),
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
            verification_sidecars = self._verification_sidecar_documents(source)
            delivery_sidecars = self._delivery_sidecar_documents(source)
            data_docs = public_trust_center_data_documents(report, verification_sidecars, delivery_sidecars)
            data_docs.update(delivery_sidecars)
            data_docs.update(verification_sidecars)
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
                "delivery_summary": {
                    "delivery_release_count": report.get("summary", {}).get("delivery_release_count"),
                    "delivery_ready_count": report.get("summary", {}).get("delivery_ready_count"),
                    "distribution_ready_count": report.get("summary", {}).get("distribution_ready_count"),
                    "submission_accepted_count": report.get("summary", {}).get("submission_accepted_count"),
                    "operations_signed_count": report.get("summary", {}).get("operations_signed_count"),
                },
                "pages": page_rows,
                "data": {
                    "trust_center_data_hash": stable_hash(data_docs["trust-center-data.json"]),
                    "package_index_hash": stable_hash(data_docs["package-index.json"]),
                    "verification_index_hash": stable_hash(data_docs["verification-index.json"]),
                    "public_package_verification_index_hash": stable_hash(data_docs["public-package-verification-index.json"]),
                    "risk_register_hash": stable_hash(data_docs["risk-register.json"]),
                    "delivery_index_hash": stable_hash(data_docs["delivery-index.json"]),
                    "distribution_index_hash": stable_hash(data_docs["distribution-index.json"]),
                    "submission_index_hash": stable_hash(data_docs["submission-index.json"]),
                    "submission_evidence_index_hash": stable_hash(data_docs["submission-evidence-index.json"]),
                    "operations_index_hash": stable_hash(data_docs["operations-index.json"]),
                    "operations_package_index_hash": stable_hash(data_docs["operations-package-index.json"]),
                    "readiness_matrix_hash": stable_hash(data_docs["readiness-matrix.json"]),
                    "delivery_risk_register_hash": stable_hash(data_docs["delivery-risk-register.json"]),
                    "delivery_verification_index_hash": stable_hash(data_docs["delivery-verification-index.json"]),
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
            self._write_delivery_anchor(center_id, manifest, zip_info)
            self._append_history(center_id, "trust_center_zip_built", {"source_hash": report.get("source_hash"), "zip_sha256": zip_info["sha256"], "manifest_hash": manifest["integrity_hash"], **state}, now=now)
            return _sanitize_public_metadata(zip_info)

    def verify_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.public_trust_center_verifier import verify_public_trust_center_package, write_public_trust_center_verification_report

        payload = payload or {}
        report = verify_public_trust_center_package(
            self.zip_path(center_id),
            strict=bool(payload.get("strict", True)),
            require_registry_current=bool(payload.get("require_registry_current", False)),
            require_portal_current=bool(payload.get("require_portal_current", False)),
            require_transparency_current=bool(payload.get("require_transparency_current", False)),
            require_acknowledgement_current=bool(payload.get("require_acknowledgement_current", False)),
            require_release_readiness=bool(payload.get("require_release_readiness", False)),
            require_delivery_readiness=bool(payload.get("require_delivery_readiness", False)),
            require_distribution_ready=bool(payload.get("require_distribution_ready", False)),
            require_submission_accepted=bool(payload.get("require_submission_accepted", False)),
            require_submission_evidence=bool(payload.get("require_submission_evidence", False)),
            require_operations_signed=bool(payload.get("require_operations_signed", False)),
            require_operations_audit=bool(payload.get("require_operations_audit", False)),
            require_operations_reviewer_pack=bool(payload.get("require_operations_reviewer_pack", False)),
            require_acceptance_board_signoff=bool(payload.get("require_acceptance_board_signoff", False)),
            delivery_anchor_path=payload.get("delivery_anchor_path") or self.delivery_anchor_path(center_id),
            anchor_registry_path=payload.get("anchor_registry_path"),
            anchor_transparency_path=payload.get("anchor_transparency_path"),
            anchor_checkpoint_path=payload.get("anchor_checkpoint_path"),
            acceptance_board_signoff_archive_path=payload.get("acceptance_board_signoff_archive_path"),
            acceptance_board_path=payload.get("acceptance_board_path"),
            acceptance_board_verification_report_path=payload.get("acceptance_board_verification_report_path"),
            distribution_kit_path=payload.get("distribution_kit_path"),
            accepted_evidence_dir=payload.get("accepted_evidence_dir"),
            require_anchor_registry_current=bool(payload.get("require_anchor_registry_current", False)),
            require_anchor_published=bool(payload.get("require_anchor_published", False)),
            require_anchor_not_revoked=bool(payload.get("require_anchor_not_revoked", False)),
            require_anchor_transparency_current=bool(payload.get("require_anchor_transparency_current", False)),
            require_anchor_checkpoint=bool(payload.get("require_anchor_checkpoint", False)),
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

    def delivery_anchor_path(self, center_id: str = "ptc-default") -> Path:
        return self.zip_path(center_id).with_name(self.zip_path(center_id).stem + ".delivery-anchor.json")

    def _write_delivery_anchor(self, center_id: str, manifest: ImplementationDocument, zip_info: ImplementationDocument) -> ImplementationDocument:
        export_dir = self.export_dir(center_id)
        rows: list[dict[str, Any]] = []
        for item in manifest.get("files", []) if isinstance(manifest.get("files"), list) else []:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            if not path.startswith("data/delivery-fingerprint-summaries/"):
                continue
            doc = _read_json_default(export_dir / path, default={})
            rows.append(
                {
                    "path": path.removeprefix("data/"),
                    "fingerprint_hash": doc.get("fingerprint_hash"),
                    "payload_hash": doc.get("payload_hash"),
                    "fingerprints_hash": stable_hash(doc.get("fingerprints") if isinstance(doc.get("fingerprints"), dict) else {}),
                }
            )
        anchor = {
            "schema_version": PTC_SCHEMA_VERSION,
            "package_type": "musicforge_public_trust_center_delivery_anchor",
            "center_id": center_id,
            "zip_sha256": zip_info.get("sha256"),
            "zip_size_bytes": zip_info.get("size_bytes"),
            "manifest_hash": manifest.get("integrity_hash"),
            "source_hash": manifest.get("source_hash"),
            "fingerprint_sidecars": sorted(rows, key=lambda row: str(row.get("path") or "")),
        }
        anchor["anchor_hash"] = stable_hash({key: value for key, value in anchor.items() if key != "anchor_hash"})
        _write_json(self.delivery_anchor_path(center_id), anchor)
        return anchor

    def _release_summaries(self, selection: ImplementationDocument) -> list[ImplementationDocument]:
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
                        "zip_size_bytes": self.release_store.zip_path(release_id).stat().st_size if self.release_store.zip_path(release_id).exists() else None,
                    }
                )
            except Exception as exc:
                rows.append({"release_id": release_id, "status": "missing", "error": str(exc)})
        return rows

    def _delivery_bundle(self, selection: ImplementationDocument, releases: list[ImplementationDocument], portfolios: list[ImplementationDocument]) -> ImplementationDocument:
        include_distribution = bool(selection.get("include_distribution", True))
        include_submission = bool(selection.get("include_submission", True))
        include_submission_evidence = bool(selection.get("include_submission_evidence", selection.get("include_submission", True)))
        include_operations = bool(selection.get("include_operations", True))
        release_ids = [str(item.get("release_id") or "") for item in releases if isinstance(item, dict) and item.get("release_id")]
        distribution = self._distribution_summaries(release_ids) if include_distribution else []
        submissions = self._submission_summaries(release_ids) if include_submission else []
        submission_evidence = self._submission_evidence_summaries(submissions) if include_submission_evidence else []
        operations = self._operations_summaries(release_ids) if include_operations else []
        operations_packages = [pkg for item in operations for pkg in item.get("package_fingerprints", []) if isinstance(pkg, dict)]
        readiness = _delivery_readiness_matrix_from_parts(releases, portfolios, distribution, submissions, submission_evidence, operations)
        risks = _delivery_risk_register_from_matrix(readiness)
        return {
            "delivery_domains": {
                "distribution": "included" if include_distribution else "excluded",
                "submission": "included" if include_submission else "excluded",
                "submission_evidence": "included" if include_submission_evidence else "excluded",
                "operations": "included" if include_operations else "excluded",
            },
            "release_delivery_summaries": readiness,
            "distribution_summaries": distribution,
            "submission_summaries": submissions,
            "submission_evidence_summaries": submission_evidence,
            "operations_summaries": operations,
            "operations_package_fingerprints": operations_packages,
            "delivery_readiness_matrix": readiness,
            "delivery_risk_register": risks,
        }

    def _distribution_summaries(self, release_ids: list[str]) -> list[ImplementationDocument]:
        if self.distribution_store is None:
            return [_domain_not_configured_row("distribution", release_id) for release_id in release_ids]
        rows: list[dict[str, Any]] = []
        for release_id in release_ids:
            try:
                targets = self.distribution_store.list_targets(release_id)
            except Exception as exc:
                rows.append({"release_id": release_id, "target_id": None, "status": "failed", "verification_status": "failed", "error": str(exc)})
                continue
            if not targets:
                rows.append({"release_id": release_id, "target_id": None, "status": "missing", "verification_status": "missing", "package_zip_status": "missing"})
                continue
            for target in targets:
                package_id = None
                try:
                    package_id = self.distribution_store.latest_package_id(target)
                except Exception:
                    package_id = None
                signoff = {}
                try:
                    signoff = self.distribution_store.read_signoff(release_id, target, default={})
                except Exception:
                    signoff = {}
                manifest_path = self.distribution_store.export_dir(release_id, package_id) / "distribution-manifest.json" if package_id else None
                manifest = _read_json_default(manifest_path, default={}) if manifest_path else {}
                zip_path = self.distribution_store.package_zip_path(release_id, package_id) if package_id else None
                verification_path = self.distribution_store.package_dir(release_id, package_id) / "verification-report.json" if package_id else None
                verification = _read_json_default(verification_path, default={}) if verification_path else {}
                qa = {}
                try:
                    qa = self.distribution_store.read_qa(release_id, target.target_id, default={})
                except Exception:
                    qa = {}
                row = {
                    "release_id": release_id,
                    "target_id": target.target_id,
                    "package_id": package_id,
                    "platform": getattr(target, "profile_id", None),
                    "profile_id": getattr(target, "profile_id", None),
                    "name": getattr(target, "name", None),
                    "status": getattr(target, "status", "missing"),
                    "signoff_status": signoff.get("status") or target.latest_signoff_summary.get("status") or "missing",
                    "package_zip_status": "exists" if zip_path and zip_path.exists() else "missing",
                    "package_zip_sha256": _sha256(zip_path) if zip_path else None,
                    "package_zip_size_bytes": zip_path.stat().st_size if zip_path and zip_path.exists() else None,
                    "manifest_hash": manifest.get("integrity_hash") or _stable_hash_without_zip(manifest),
                    "verification_status": _package_report_current_status(verification, zip_path, manifest),
                    "verification_hash": _verification_hash(verification),
                    "verification_report_status": verification.get("status") or "missing",
                    "checklist_status": _nested_status(manifest, ("checklist", "status"), default=qa.get("status") or "missing"),
                    "rights_status": _nested_status(manifest, ("rights_clearance", "status"), default="missing"),
                    "format_decision_status": _nested_status(manifest, ("format_decision", "status"), default="missing"),
                    "encoded_audio_status": _nested_status(manifest, ("encoded_audio", "status"), default="missing"),
                    "template_pack_id": getattr(target, "template_pack_id", None),
                    "updated_at": getattr(target, "updated_at", None),
                }
                row["fingerprint_hash"] = stable_hash(row)
                rows.append(_sanitize_public_metadata(row))
        return sorted(rows, key=lambda item: (str(item.get("release_id")), str(item.get("target_id"))))

    def _submission_summaries(self, release_ids: list[str]) -> list[ImplementationDocument]:
        if self.submission_store is None:
            return [_domain_not_configured_row("submission", release_id) for release_id in release_ids]
        rows: list[dict[str, Any]] = []
        for release_id in release_ids:
            try:
                submissions = self.submission_store.list_submissions(release_id)
            except Exception as exc:
                rows.append({"release_id": release_id, "submission_id": None, "status": "failed", "verification_status": "failed", "error": str(exc)})
                continue
            if not submissions:
                rows.append({"release_id": release_id, "submission_id": None, "status": "missing", "verification_status": "missing", "package_zip_status": "missing"})
                continue
            for batch in submissions:
                manifest_path = self.submission_store.export_dir(release_id, batch.submission_id) / "submission-manifest.json"
                manifest = _read_json_default(manifest_path, default={})
                zip_path = self.submission_store.package_zip_path(release_id, batch.submission_id)
                verification_path = self.submission_store.submission_dir(release_id, batch.submission_id) / "submission-verification-report.json"
                verification = _read_json_default(verification_path, default={})
                signoff = self.submission_store.read_signoff(release_id, batch.submission_id, default={})
                items = batch.items
                row = {
                    "release_id": release_id,
                    "submission_id": batch.submission_id,
                    "status": batch.status,
                    "signoff_status": signoff.get("status") or batch.latest_signoff_summary.get("status") or "missing",
                    "target_count": len(items),
                    "ready_count": sum(1 for item in items if item.status == "ready"),
                    "submitted_count": sum(1 for item in items if item.status in {"submitted", "feedback_received", "needs_changes", "accepted", "rejected"}),
                    "accepted_count": sum(1 for item in items if item.status == "accepted"),
                    "package_zip_status": "exists" if zip_path.exists() else "missing",
                    "package_zip_sha256": _sha256(zip_path),
                    "package_zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
                    "manifest_hash": manifest.get("integrity_hash") or _stable_hash_without_zip(manifest),
                    "verification_status": _package_report_current_status(verification, zip_path, manifest),
                    "verification_hash": _verification_hash(verification),
                    "verification_report_status": verification.get("status") or "missing",
                    "latest_feedback_status": _latest_feedback_status(items),
                    "updated_at": batch.updated_at,
                }
                row["fingerprint_hash"] = stable_hash(row)
                rows.append(_sanitize_public_metadata(row))
        return sorted(rows, key=lambda item: (str(item.get("release_id")), str(item.get("submission_id"))))

    def _submission_evidence_summaries(self, submissions: list[ImplementationDocument]) -> list[ImplementationDocument]:
        if self.submission_evidence_store is None:
            return [_domain_not_configured_row("submission_evidence", str(item.get("release_id") or ""), submission_id=item.get("submission_id")) for item in submissions if item.get("submission_id")]
        rows: list[dict[str, Any]] = []
        for item in submissions:
            release_id = str(item.get("release_id") or "")
            submission_id = str(item.get("submission_id") or "")
            if not release_id or not submission_id:
                continue
            report = self.submission_evidence_store.read_report(release_id, submission_id, default={})
            signoff = self.submission_evidence_store.read_signoff(release_id, submission_id, default={})
            manifest_path = self.submission_evidence_store.export_dir(release_id, submission_id) / "submission-evidence-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            zip_path = self.submission_evidence_store.package_zip_path(release_id, submission_id)
            verification_path = self.submission_store.submission_dir(release_id, submission_id) / "submission-evidence-verification-report.json" if self.submission_store else None
            verification = _read_json_default(verification_path, default={}) if verification_path else {}
            summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
            row = {
                "release_id": release_id,
                "submission_id": submission_id,
                "report_status": report.get("status") or "missing",
                "report_hash": report.get("integrity_hash"),
                "signoff_status": signoff.get("status") or "missing",
                "signoff_hash": signoff.get("payload_hash"),
                "package_zip_status": "exists" if zip_path.exists() else "missing",
                "package_zip_sha256": _sha256(zip_path),
                "package_zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
                "manifest_hash": manifest.get("integrity_hash") or _stable_hash_without_zip(manifest),
                "verification_status": _package_report_current_status(verification, zip_path, manifest),
                "verification_hash": _verification_hash(verification),
                "verification_report_status": verification.get("status") or "missing",
                "accepted_evidence_count": summary.get("accepted_count", 0),
                "attachment_count": summary.get("attachment_count", 0),
                "redaction_status": (manifest.get("redaction_summary") if isinstance(manifest.get("redaction_summary"), dict) else {}).get("status") or "missing",
            }
            row["fingerprint_hash"] = stable_hash(row)
            rows.append(_sanitize_public_metadata(row))
        return sorted(rows, key=lambda row: (str(row.get("release_id")), str(row.get("submission_id"))))

    def _operations_summaries(self, release_ids: list[str]) -> list[ImplementationDocument]:
        if self.operations_store is None:
            return [_domain_not_configured_row("operations", release_id) for release_id in release_ids]
        rows: list[dict[str, Any]] = []
        for release_id in release_ids:
            report = self.operations_store.read_report(release_id, default={})
            report_summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
            report_status = report.get("status") or "missing"
            signoff = self.operations_signoff_store.read_signoff(release_id, default={}) if self.operations_signoff_store is not None else {}
            report_signoff = report_summary.get("operations_signoff") if isinstance(report_summary.get("operations_signoff"), dict) else {}
            signoff_status = signoff.get("status") or report_signoff.get("status")
            runbook_summary = self._latest_runbook_summary(release_id)
            packages = self._operations_package_fingerprints(release_id)
            audit_summary = self.operations_audit_store.summary(release_id) if self.operations_audit_store is not None else {"status": "not_configured"}
            reviewer_summary = self.operations_reviewer_pack_store.summary(release_id) if self.operations_reviewer_pack_store is not None else {"status": "not_configured"}
            row = {
                "release_id": release_id,
                "operations_report_status": report_status,
                "operations_report_hash": report.get("integrity_hash"),
                "operations_source_hash": report.get("source_hash"),
                "operations_signoff_status": signoff_status or "missing",
                "operations_signoff_hash": signoff.get("payload_hash"),
                "operations_archive_status": _package_status_from_fingerprints(packages, "operations_archive"),
                "operations_audit_status": audit_summary.get("status") or _package_status_from_fingerprints(packages, "operations_audit"),
                "operations_reviewer_pack_status": reviewer_summary.get("status") or _package_status_from_fingerprints(packages, "operations_reviewer_pack"),
                "runbook_status": runbook_summary.get("status") or "missing",
                "change_request_count": len(self.operations_signoff_store.list_change_requests(release_id)) if self.operations_signoff_store is not None else 0,
                "package_fingerprints": packages,
            }
            row["fingerprint_hash"] = stable_hash(row)
            rows.append(_sanitize_public_metadata(row))
        return sorted(rows, key=lambda row: str(row.get("release_id") or ""))

    def _latest_runbook_summary(self, release_id: str) -> ImplementationDocument:
        if self.operations_runbook_store is None:
            return {"status": "not_configured"}
        try:
            rows = self.operations_runbook_store.list_runbooks(release_id, include_archived=True)
        except Exception:
            return {"status": "missing"}
        if not rows:
            return {"status": "missing"}
        latest = rows[0]
        return {
            "runbook_id": latest.get("runbook_id"),
            "status": latest.get("status") or "missing",
            "source_hash": (latest.get("source") if isinstance(latest.get("source"), dict) else {}).get("operations_source_hash"),
            "integrity_hash": latest.get("integrity_hash"),
        }

    def _operations_package_fingerprints(self, release_id: str) -> list[ImplementationDocument]:
        rows: list[dict[str, Any]] = []
        if self.operations_store is not None:
            rows.append(self._generic_package_fingerprint(
                "operations",
                release_id,
                self.operations_store.zip_path(release_id),
                self.operations_store.export_dir(release_id) / "operations-manifest.json",
                self.operations_store.operations_dir(release_id) / "operations-verification-report.json",
            ))
        if self.operations_signoff_store is not None:
            rows.append(self._generic_package_fingerprint(
                "operations_archive",
                release_id,
                self.operations_signoff_store.archive_zip_path(release_id),
                self.operations_signoff_store.archive_export_dir(release_id) / "operations-archive-manifest.json",
                self.operations_signoff_store.operations_dir(release_id) / "operations-archive-verification-report.json",
            ))
        if self.operations_audit_store is not None:
            rows.append(self._generic_package_fingerprint(
                "operations_audit",
                release_id,
                self.operations_audit_store.zip_path(release_id),
                self.operations_audit_store.export_dir(release_id) / "operations-audit-manifest.json",
                self.operations_audit_store.verification_report_path(release_id),
            ))
        if self.operations_reviewer_pack_store is not None:
            rows.append(self._generic_package_fingerprint(
                "operations_reviewer_pack",
                release_id,
                self.operations_reviewer_pack_store.zip_path(release_id),
                self.operations_reviewer_pack_store.export_dir(release_id) / "reviewer-pack-manifest.json",
                self.operations_reviewer_pack_store.verification_report_path(release_id),
            ))
        return [row for row in rows if row]

    def _generic_package_fingerprint(self, package_type: str, release_id: str, zip_path: Path, manifest_path: Path, verification_report_path: Path) -> ImplementationDocument:
        manifest = _read_json_default(manifest_path, default={})
        verification = _read_json_default(verification_report_path, default={})
        row = {
            "release_id": release_id,
            "package_type": package_type,
            "zip_sha256": _sha256(zip_path),
            "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
            "manifest_hash": manifest.get("integrity_hash") or _stable_hash_without_zip(manifest),
            "verification_status": _package_report_current_status(verification, zip_path, manifest),
            "verification_hash": _verification_hash(verification),
            "verification_report_status": verification.get("status") or "missing",
        }
        row["fingerprint_hash"] = stable_hash(row)
        return _sanitize_public_metadata(row)

    def _portfolio_summaries(self, selection: ImplementationDocument, *, profile: str) -> list[ImplementationDocument]:
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

    def _portfolio_summary(self, portfolio_id: str, *, profile: str) -> ImplementationDocument:
        portfolio = {}
        try:
            portfolio = self.portfolio_store.get_portfolio(portfolio_id)
        except Exception:
            portfolio = {"portfolio_id": portfolio_id, "status": "missing"}
        registry = self._package_summary("registry", portfolio_id, profile, self.registry_store.zip_path(portfolio_id, profile), self.registry_store.export_dir(portfolio_id, profile) / "manifest.json", self.registry_store.verification_report_path(portfolio_id, profile))
        portal = self._package_summary("portal", portfolio_id, profile, self.portal_store.zip_path(portfolio_id, profile), self.portal_store.export_dir(portfolio_id, profile) / "portal-manifest.json", self.portal_store.verification_report_path(portfolio_id, profile))
        transparency = self._package_summary("transparency", portfolio_id, profile, self.transparency_store.zip_path(portfolio_id, profile), self.transparency_store.export_dir(portfolio_id, profile) / "transparency-manifest.json", self.transparency_store.verification_report_path(portfolio_id, profile))
        ack = self._package_summary("transparency_acknowledgement", portfolio_id, profile, self.acknowledgement_store.evidence_zip_path(portfolio_id, profile), self.acknowledgement_store.evidence_export_dir(portfolio_id, profile) / "acknowledgement-evidence-manifest.json", self.acknowledgement_store.evidence_verification_report_path(portfolio_id, profile))
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

    def _package_summary(self, package_type: str, portfolio_id: str, profile: str, zip_path: Path, manifest_path: Path, verification_report_path: Path) -> ImplementationDocument:
        manifest = _read_json_default(manifest_path, default={})
        summary: dict[str, Any] = {}
        verification = _read_json_default(verification_report_path, default={})
        current_zip_sha256 = _sha256(zip_path)
        current_zip_size = zip_path.stat().st_size if zip_path.exists() and zip_path.is_file() else None
        current_manifest_hash = manifest.get("integrity_hash") if isinstance(manifest, dict) else None
        verification_hash = _verification_hash(verification)
        verification_status = _verification_current_status(verification, current_zip_sha256, current_zip_size, current_manifest_hash)
        package = {
            "portfolio_id": portfolio_id,
            "profile": profile,
            "package_type": package_type,
            "zip_sha256": current_zip_sha256,
            "zip_size_bytes": current_zip_size,
            "manifest_hash": current_manifest_hash or verification.get("manifest_hash"),
            "verification_hash": verification_hash,
            "verification_status": verification_status,
            "verification_report_hash": verification_hash,
            "verification_report_status": verification.get("status") or "missing",
        }
        if isinstance(verification.get("summary"), dict):
            summary = dict(verification["summary"])
        return {"package": package, "verification": {**package, "blocker_count": len(verification.get("blockers", []) if isinstance(verification.get("blockers"), list) else [])}, "summary": summary}

    def _verification_sidecar_documents(self, source: ImplementationDocument) -> dict[str, ImplementationDocument]:
        docs: dict[str, dict[str, Any]] = {}
        for item in source.get("public_package_fingerprints", []) if isinstance(source.get("public_package_fingerprints"), list) else []:
            if not isinstance(item, dict):
                continue
            portfolio_id = str(item.get("portfolio_id") or "")
            profile = str(item.get("profile") or "public_summary")
            package_type = str(item.get("package_type") or "")
            report_path = self._stored_verification_report_path(package_type, portfolio_id, profile)
            verification_report = _read_json_default(report_path, default={}) if report_path else {}
            path = _verification_sidecar_path(portfolio_id, profile, package_type)
            docs[path] = _verification_sidecar_document(item, verification_report)
        return docs

    def _delivery_sidecar_documents(self, source: ImplementationDocument) -> dict[str, ImplementationDocument]:
        docs: dict[str, dict[str, Any]] = {}
        for collection, domain in _DELIVERY_COLLECTION_DOMAINS:
            rows = source.get(collection, []) if isinstance(source.get(collection), list) else []
            for item in rows:
                if not isinstance(item, dict):
                    continue
                release_id = str(item.get("release_id") or "")
                entity_id = str(item.get("target_id") or item.get("submission_id") or item.get("release_id") or "summary")
                if not release_id:
                    continue
                summary_path = _delivery_sidecar_path(domain, release_id, entity_id)
                fingerprint_path = _delivery_fingerprint_sidecar_path(domain, release_id, entity_id)
                independent_item = self._independent_delivery_sidecar_item(domain, item)
                fingerprint_doc = _delivery_fingerprint_sidecar_document(domain, independent_item, fingerprint_path)
                docs[summary_path] = _delivery_sidecar_document(domain, independent_item, fingerprint_path=fingerprint_path, fingerprint_hash=stable_hash(fingerprint_doc))
                docs[fingerprint_path] = fingerprint_doc
        return docs

    def _independent_delivery_sidecar_item(self, domain: str, item: ImplementationDocument) -> ImplementationDocument:
        release_id = str(item.get("release_id") or "")
        if not release_id:
            return item
        try:
            if domain == "release":
                releases = self._release_summaries({"release_ids": [release_id], "include_all_releases": False})
                distribution = self._distribution_summaries([release_id])
                submissions = self._submission_summaries([release_id])
                submission_evidence = self._submission_evidence_summaries(submissions)
                operations = self._operations_summaries([release_id])
                rows = _delivery_readiness_matrix_from_parts(releases, [], distribution, submissions, submission_evidence, operations)
                if rows:
                    row = dict(rows[0])
                    if "portfolio_public_proof_status" in item:
                        row["portfolio_public_proof_status"] = item.get("portfolio_public_proof_status")
                        row.pop("fingerprint_hash", None)
                        row["fingerprint_hash"] = stable_hash(row)
                    return row
                return dict(item)
            if domain == "distribution":
                return self._matching_delivery_row(self._distribution_summaries([release_id]), item, "target_id")
            if domain == "submission":
                return self._matching_delivery_row(self._submission_summaries([release_id]), item, "submission_id")
            if domain == "submission_evidence":
                submissions = self._submission_summaries([release_id])
                return self._matching_delivery_row(self._submission_evidence_summaries(submissions), item, "submission_id")
            if domain == "operations":
                return self._matching_delivery_row(self._operations_summaries([release_id]), item, "release_id")
        except Exception as exc:
            fallback = dict(item)
            fallback["status"] = "failed"
            fallback["verification_status"] = "failed"
            fallback["error"] = str(exc)
            return fallback
        return item

    @staticmethod
    def _matching_delivery_row(rows: list[ImplementationDocument], item: ImplementationDocument, key: str) -> ImplementationDocument:
        wanted = str(item.get(key) or "")
        if wanted:
            for row in rows:
                if str(row.get(key) or "") == wanted:
                    return row
        return rows[0] if rows else dict(item)

    def _stored_verification_report_path(self, package_type: str, portfolio_id: str, profile: str) -> Path | None:
        if package_type == "registry":
            return self.registry_store.verification_report_path(portfolio_id, profile)
        if package_type == "portal":
            return self.portal_store.verification_report_path(portfolio_id, profile)
        if package_type == "transparency":
            return self.transparency_store.verification_report_path(portfolio_id, profile)
        if package_type == "transparency_acknowledgement":
            return self.acknowledgement_store.evidence_verification_report_path(portfolio_id, profile)
        return None

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

    def _ensure_exportable(self, report: ImplementationDocument, source: ImplementationDocument) -> None:
        if not report:
            raise PublicTrustCenterStateError("Public Trust Center report has not been generated.")
        if str(report.get("source_hash") or "") != stable_hash(source):
            raise PublicTrustCenterStateError("Public Trust Center source is stale. Refresh before export.")
        if not public_trust_center_report_integrity_ok(report):
            raise PublicTrustCenterStateError("Public Trust Center report integrity failed.")

    def _append_history(self, center_id: str, event_type: str, payload: ImplementationDocument, *, now: str | None = None) -> None:
        path = self.history_path(center_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event_type": event_type, "created_at": now or now_iso(), "payload": sanitize_metadata(payload, blocked_keys=PTC_BLOCKED_KEYS)}, ensure_ascii=False, sort_keys=True) + "\n")

    def _history_has_state_event(self, center_id: str, state: ImplementationDocument, event_type: str) -> bool:
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
    delivery_rows = source.get("release_delivery_summaries", []) if isinstance(source.get("release_delivery_summaries"), list) else []
    distribution_rows = source.get("distribution_summaries", []) if isinstance(source.get("distribution_summaries"), list) else []
    submission_rows = source.get("submission_summaries", []) if isinstance(source.get("submission_summaries"), list) else []
    operations_rows = source.get("operations_summaries", []) if isinstance(source.get("operations_summaries"), list) else []
    return {
        "center_id": source.get("center_id"),
        "profile": source.get("profile"),
        "release_count": int(source.get("release_count") or 0),
        "portfolio_count": int(source.get("portfolio_count") or 0),
        "public_package_count": package_count,
        "verification_count": verification_count,
        "passed_verification_count": passed_verifications,
        "delivery_release_count": len(delivery_rows),
        "delivery_ready_count": sum(1 for item in delivery_rows if isinstance(item, dict) and item.get("readiness") == "ready"),
        "distribution_ready_count": sum(1 for item in distribution_rows if isinstance(item, dict) and item.get("readiness") == "ready"),
        "submission_accepted_count": sum(1 for item in submission_rows if isinstance(item, dict) and item.get("accepted_count", 0)),
        "operations_signed_count": sum(1 for item in operations_rows if isinstance(item, dict) and item.get("operations_signoff_status") in {"signed", "force_signed"}),
        "delivery_risk_count": len(source.get("delivery_risk_register", []) if isinstance(source.get("delivery_risk_register"), list) else []),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "readiness": "blocked" if blockers else "review_needed" if warnings else "public_trust_ready",
    }











def _normalize_selection(payload: ImplementationDocument) -> ImplementationDocument:
    return {
        "release_ids": [str(item).strip() for item in payload.get("release_ids", []) if str(item).strip()] if isinstance(payload.get("release_ids"), list) else [],
        "portfolio_ids": [str(item).strip() for item in payload.get("portfolio_ids", []) if str(item).strip()] if isinstance(payload.get("portfolio_ids"), list) else [],
        "include_all_releases": bool(payload.get("include_all_releases", True)),
        "include_all_portfolios": bool(payload.get("include_all_portfolios", True)),
        "attestation_profile": str(payload.get("attestation_profile") or payload.get("profile") or "public_summary"),
        "include_distribution": bool(payload.get("include_distribution", payload.get("include_delivery", True))),
        "include_submission": bool(payload.get("include_submission", payload.get("include_delivery", True))),
        "include_submission_evidence": bool(payload.get("include_submission_evidence", payload.get("include_submission", payload.get("include_delivery", True)))),
        "include_operations": bool(payload.get("include_operations", payload.get("include_delivery", True))),
    }


def _normalize_policy(payload: ImplementationDocument) -> ImplementationDocument:
    return {
        "require_registry_current": bool(payload.get("require_registry_current", True)),
        "require_portal_current": bool(payload.get("require_portal_current", True)),
        "require_transparency_current": bool(payload.get("require_transparency_current", True)),
        "require_acknowledgement_current": bool(payload.get("require_acknowledgement_current", False)),
        "require_release_signoff": bool(payload.get("require_release_signoff", True)),
        "require_distribution_signed": bool(payload.get("require_distribution_signed", False)),
        "require_submission_accepted": bool(payload.get("require_submission_accepted", False)),
        "require_submission_evidence_signed": bool(payload.get("require_submission_evidence_signed", False)),
        "require_operations_signed": bool(payload.get("require_operations_signed", False)),
        "require_operations_audit_verified": bool(payload.get("require_operations_audit_verified", False)),
        "require_operations_reviewer_pack_verified": bool(payload.get("require_operations_reviewer_pack_verified", False)),
    }


def _findings_from_source(source: ImplementationDocument) -> tuple[list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
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
    delivery_required = {
        "release_signoff": bool(policy.get("require_release_signoff", True)),
        "distribution_signed": bool(policy.get("require_distribution_signed", False)),
        "submission_accepted": bool(policy.get("require_submission_accepted", False)),
        "submission_evidence_signed": bool(policy.get("require_submission_evidence_signed", False)),
        "operations_signed": bool(policy.get("require_operations_signed", False)),
        "operations_audit_verified": bool(policy.get("require_operations_audit_verified", False)),
        "operations_reviewer_pack_verified": bool(policy.get("require_operations_reviewer_pack_verified", False)),
    }
    readiness = source.get("delivery_readiness_matrix", []) if isinstance(source.get("delivery_readiness_matrix"), list) else []
    if delivery_required["release_signoff"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("release_signoff_status") not in {"signed", "force_signed"}]
        if failed:
            blockers.append(_finding("release_signoff_required", "critical", "One or more releases are missing Release Signoff."))
    if delivery_required["distribution_signed"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("distribution_status") not in {"ready"}]
        if failed:
            blockers.append(_finding("distribution_signed_required", "critical", "Distribution readiness is required but not complete."))
    if delivery_required["submission_accepted"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("submission_status") not in {"accepted"}]
        if failed:
            blockers.append(_finding("submission_accepted_required", "critical", "Submission accepted status is required but missing."))
    if delivery_required["submission_evidence_signed"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("submission_evidence_status") not in {"signed"}]
        if failed:
            blockers.append(_finding("submission_evidence_signed_required", "critical", "Submission Evidence signoff is required but missing."))
    if delivery_required["operations_signed"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("operations_status") not in {"signed", "force_signed"}]
        if failed:
            blockers.append(_finding("operations_signed_required", "critical", "Release Operations signoff is required but missing."))
    if delivery_required["operations_audit_verified"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("operations_audit_status") not in {"passed", "warning"}]
        if failed:
            blockers.append(_finding("operations_audit_required", "critical", "Release Operations Audit verification is required but missing."))
    if delivery_required["operations_reviewer_pack_verified"]:
        failed = [item for item in readiness if isinstance(item, dict) and item.get("operations_reviewer_pack_status") not in {"passed", "warning"}]
        if failed:
            blockers.append(_finding("operations_reviewer_pack_required", "critical", "Release Operations Reviewer Pack verification is required but missing."))
    delivery_blocker_ids = {
        "release_signoff": "release_signoff_required",
        "distribution_signed": "distribution_signed_required",
        "submission_accepted": "submission_accepted_required",
        "submission_evidence_signed": "submission_evidence_signed_required",
        "operations_signed": "operations_signed_required",
        "operations_audit_verified": "operations_audit_required",
        "operations_reviewer_pack_verified": "operations_reviewer_pack_required",
    }
    for check_id, enabled in delivery_required.items():
        if not enabled:
            checks.append({"check_id": f"ptc_{check_id}", "status": "passed", "severity": "blocking", "message": f"{check_id} is not required."})
            continue
        failed = [item for item in blockers if str(item.get("check_id") or "") == delivery_blocker_ids.get(check_id)]
        checks.append({"check_id": f"ptc_{check_id}", "status": "failed" if failed else "passed", "severity": "blocking", "message": f"{check_id} {'failed' if failed else 'passed'}."})
    checks.append({"check_id": "ptc_source_redaction", "status": "passed" if _redaction_summary(source)["status"] == "passed" else "failed", "severity": "blocking", "message": "Public Trust Center source redaction scan completed."})
    if _redaction_summary(source)["status"] != "passed":
        blockers.append(_finding("source_redaction", "critical", "Public Trust Center source contains sensitive values."))
    return blockers, warnings, checks


def _release_readiness(source: ImplementationDocument) -> list[ImplementationDocument]:
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


def _delivery_readiness(source: ImplementationDocument) -> list[ImplementationDocument]:
    return sorted([dict(item) for item in source.get("delivery_readiness_matrix", []) if isinstance(item, dict)], key=lambda item: str(item.get("release_id") or ""))


def _portfolio_readiness(source: ImplementationDocument) -> list[ImplementationDocument]:
    rows = []
    for item in source.get("portfolios", []) if isinstance(source.get("portfolios"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append({"portfolio_id": item.get("portfolio_id"), "status": item.get("status"), "profile": item.get("profile"), "public_package_status": item.get("public_package_status")})
    return sorted(rows, key=lambda item: str(item.get("portfolio_id") or ""))

















def _verification_sidecar_document(package: ImplementationDocument, verification_report: ImplementationDocument) -> ImplementationDocument:
    verification_hash = _verification_hash(verification_report)
    doc = {
        "schema_version": PTC_SCHEMA_VERSION,
        "package_type": "musicforge_public_trust_center_package_verification_summary",
        "sidecar_path": _verification_sidecar_path(str(package.get("portfolio_id") or ""), str(package.get("profile") or "public_summary"), str(package.get("package_type") or "")),
        "portfolio_id": package.get("portfolio_id"),
        "profile": package.get("profile"),
        "public_package_type": package.get("package_type"),
        "package": {
            "portfolio_id": package.get("portfolio_id"),
            "profile": package.get("profile"),
            "package_type": package.get("package_type"),
            "zip_sha256": package.get("zip_sha256"),
            "zip_size_bytes": package.get("zip_size_bytes"),
            "manifest_hash": package.get("manifest_hash"),
            "verification_hash": verification_hash,
            "verification_status": _verification_current_status(verification_report, package.get("zip_sha256"), package.get("zip_size_bytes"), package.get("manifest_hash")),
            "verification_report_hash": verification_hash,
            "verification_report_status": verification_report.get("status") or "missing",
        },
        "verification": {
            "verification_report_hash": verification_hash,
            "verification_report_status": verification_report.get("status") or "missing",
            "zip_sha256": verification_report.get("zip_sha256"),
            "zip_size_bytes": verification_report.get("zip_size_bytes"),
            "manifest_hash": verification_report.get("manifest_hash"),
            "blocker_count": len(verification_report.get("blockers", []) if isinstance(verification_report.get("blockers"), list) else []),
            "warning_count": len(verification_report.get("warnings", []) if isinstance(verification_report.get("warnings"), list) else []),
        },
    }
    doc["summary_hash"] = stable_hash({"package": doc["package"], "verification": doc["verification"]})
    return _sanitize_public_metadata(doc)








def _delivery_sidecar_document(domain: str, item: ImplementationDocument, *, fingerprint_path: str | None = None, fingerprint_hash: str | None = None) -> ImplementationDocument:
    summary = _delivery_summary_from_item(domain, item)
    payload = _delivery_public_payload(domain, item)
    evidence = _delivery_sidecar_evidence(domain, item, payload)
    if fingerprint_path:
        summary["fingerprint_sidecar_path"] = fingerprint_path
    if fingerprint_hash:
        summary["fingerprint_sidecar_hash"] = fingerprint_hash
    doc = {
        "schema_version": PTC_SCHEMA_VERSION,
        "package_type": "musicforge_public_trust_center_delivery_verification_summary",
        "sidecar_path": _delivery_sidecar_path(domain, str(item.get("release_id") or ""), str(item.get("target_id") or item.get("submission_id") or item.get("release_id") or "summary")),
        "release_id": item.get("release_id"),
        "domain": domain,
        "entity_id": summary.get("entity_id"),
        "fingerprint_sidecar_path": fingerprint_path,
        "fingerprint_sidecar_hash": fingerprint_hash,
        "summary": summary,
        "payload": payload,
        "evidence": evidence,
        "source_hash": stable_hash(item),
    }
    doc["summary_hash"] = stable_hash({"summary": summary, "payload": payload, "evidence": evidence})
    return _sanitize_public_metadata(doc)


def _delivery_fingerprint_sidecar_document(domain: str, item: ImplementationDocument, sidecar_path: str) -> ImplementationDocument:
    payload = _delivery_public_payload(domain, item)
    fingerprints = _delivery_bottom_fingerprints(domain, item)
    doc = {
        "schema_version": PTC_SCHEMA_VERSION,
        "package_type": "musicforge_public_trust_center_delivery_fingerprint_summary",
        "sidecar_path": sidecar_path,
        "release_id": item.get("release_id"),
        "domain": domain,
        "entity_id": str(item.get("target_id") or item.get("submission_id") or item.get("release_id") or ""),
        "payload": payload,
        "payload_hash": stable_hash(payload),
        "fingerprints": fingerprints,
    }
    doc["fingerprint_hash"] = stable_hash({"payload_hash": doc["payload_hash"], "fingerprints": fingerprints})
    return _sanitize_public_metadata(doc)


def _delivery_bottom_fingerprints(domain: str, item: ImplementationDocument) -> ImplementationDocument:
    keys = {
        "release_id",
        "target_id",
        "submission_id",
        "package_id",
        "signoff_status",
        "signoff_hash",
        "release_signoff_status",
        "release_zip_status",
        "zip_sha256",
        "zip_size_bytes",
        "export_manifest_hash",
        "package_zip_status",
        "package_zip_sha256",
        "package_zip_size_bytes",
        "manifest_hash",
        "verification_status",
        "verification_hash",
        "verification_report_status",
        "report_status",
        "report_hash",
        "operations_report_status",
        "operations_report_hash",
        "operations_source_hash",
        "operations_signoff_status",
        "operations_signoff_hash",
        "operations_archive_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "runbook_status",
        "fingerprint_hash",
    }
    return {"domain": domain, **{key: item.get(key) for key in sorted(keys) if key in item}}


def _delivery_sidecar_evidence(domain: str, item: ImplementationDocument, payload: ImplementationDocument) -> ImplementationDocument:
    evidence_keys = {
        "release_id",
        "target_id",
        "submission_id",
        "package_id",
        "status",
        "signoff_status",
        "signoff_hash",
        "release_signoff_status",
        "release_zip_status",
        "package_zip_status",
        "package_zip_sha256",
        "package_zip_size_bytes",
        "manifest_hash",
        "verification_status",
        "verification_hash",
        "verification_report_status",
        "operations_report_status",
        "operations_report_hash",
        "operations_source_hash",
        "operations_signoff_status",
        "operations_signoff_hash",
        "operations_archive_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "readiness",
        "risk_count",
        "distribution_status",
        "submission_status",
        "submission_evidence_status",
        "operations_status",
        "portfolio_public_proof_status",
        "fingerprint_hash",
    }
    evidence = {
        "domain": domain,
        "payload": payload,
        "payload_hash": stable_hash(payload),
        "store_snapshot_hash": stable_hash({key: item.get(key) for key in sorted(evidence_keys) if key in item}),
    }
    for key in sorted(evidence_keys):
        if key in item:
            evidence[key] = item.get(key)
    return evidence

















def _verification_sidecar_path(portfolio_id: str, profile: str, package_type: str) -> str:
    parts = [_safe_id(portfolio_id), _safe_id(profile or "public_summary"), _safe_id(package_type or "unknown")]
    return "package-verification-summaries/" + "__".join(parts) + ".json"


def _delivery_sidecar_path(domain: str, release_id: str, entity_id: str) -> str:
    parts = [_safe_id(release_id), _safe_id(domain or "delivery"), _safe_id(entity_id or "summary")]
    return "delivery-verification-summaries/" + "__".join(parts) + ".json"


def _delivery_fingerprint_sidecar_path(domain: str, release_id: str, entity_id: str) -> str:
    parts = [_safe_id(release_id), _safe_id(domain or "delivery"), _safe_id(entity_id or "summary")]
    return "delivery-fingerprint-summaries/" + "__".join(parts) + ".json"


def _risk_register(source: ImplementationDocument, blockers: list[ImplementationDocument], warnings: list[ImplementationDocument]) -> list[ImplementationDocument]:
    risks: list[dict[str, Any]] = []
    for index, item in enumerate(blockers, start=1):
        risks.append({"risk_id": f"ptc-risk_{index:03d}", "severity": "critical", "category": item.get("check_id"), "title": item.get("message"), "source": "blocker"})
    offset = len(risks)
    for index, item in enumerate(warnings, start=1):
        risks.append({"risk_id": f"ptc-risk_{offset + index:03d}", "severity": "warning", "category": item.get("check_id"), "title": item.get("message"), "source": "warning"})
    if not risks and int(source.get("portfolio_count") or 0) > 0:
        risks.append({"risk_id": "ptc-risk_000", "severity": "info", "category": "ready", "title": "Public trust evidence is current.", "source": "system"})
    return risks


def _delivery_risk_register(source: ImplementationDocument) -> list[ImplementationDocument]:
    return sorted([dict(item) for item in source.get("delivery_risk_register", []) if isinstance(item, dict)], key=lambda item: str(item.get("risk_id") or ""))


def _delivery_readiness_matrix_from_parts(
    releases: list[ImplementationDocument],
    portfolios: list[ImplementationDocument],
    distribution: list[ImplementationDocument],
    submissions: list[ImplementationDocument],
    submission_evidence: list[ImplementationDocument],
    operations: list[ImplementationDocument],
) -> list[ImplementationDocument]:
    portfolio_status = _aggregate_status([item.get("public_package_status") for item in portfolios if isinstance(item, dict)])
    rows: list[dict[str, Any]] = []
    for release in releases:
        if not isinstance(release, dict):
            continue
        release_id = str(release.get("release_id") or "")
        dist_rows = [item for item in distribution if isinstance(item, dict) and item.get("release_id") == release_id]
        sub_rows = [item for item in submissions if isinstance(item, dict) and item.get("release_id") == release_id]
        evidence_rows = [item for item in submission_evidence if isinstance(item, dict) and item.get("release_id") == release_id]
        ops_rows = [item for item in operations if isinstance(item, dict) and item.get("release_id") == release_id]
        row = {
            "release_id": release_id,
            "name": release.get("name"),
            "status": release.get("status"),
            "release_signoff_status": release.get("signoff_status") or "missing",
            "release_zip_status": "exists" if release.get("zip_sha256") else "missing",
            "distribution_status": _distribution_status(dist_rows),
            "submission_status": _submission_status(sub_rows),
            "submission_evidence_status": _submission_evidence_status(evidence_rows),
            "operations_status": _operations_status(ops_rows),
            "operations_audit_status": _operations_audit_status(ops_rows),
            "operations_reviewer_pack_status": _operations_reviewer_pack_status(ops_rows),
            "portfolio_public_proof_status": portfolio_status,
        }
        risk_count = len(_delivery_risks_for_row(row))
        row["risk_count"] = risk_count
        row["readiness"] = "ready" if risk_count == 0 and row["release_signoff_status"] in {"signed", "force_signed"} else "blocked" if _has_blocking_delivery_status(row) else "review_needed"
        row["fingerprint_hash"] = stable_hash(row)
        rows.append(_sanitize_public_metadata(row))
    return sorted(rows, key=lambda item: str(item.get("release_id") or ""))


def _delivery_risk_register_from_matrix(rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    risks: list[dict[str, Any]] = []
    for row in rows:
        risks.extend(_delivery_risks_for_row(row))
    if not risks and rows:
        risks.append({"risk_id": "ptc-delivery-risk-000000", "release_id": None, "domain": "delivery", "severity": "info", "status": "closed", "title": "Delivery evidence has no critical gaps.", "public_safe_detail": "All selected Release delivery summaries are ready or non-required."})
    for index, risk in enumerate(risks, start=1):
        risk["risk_id"] = f"ptc-delivery-risk-{index:06d}"
    return risks


def _delivery_risks_for_row(row: ImplementationDocument) -> list[ImplementationDocument]:
    release_id = row.get("release_id")
    checks = [
        ("release", row.get("release_signoff_status") in {"signed", "force_signed"}, "Release Signoff is missing."),
        ("release_zip", row.get("release_zip_status") == "exists", "Release ZIP is missing."),
        ("distribution", row.get("distribution_status") in {"ready", "not_configured"}, "Distribution package is not fully signed and verified."),
        ("submission", row.get("submission_status") in {"accepted", "not_configured", "missing"}, "Submission is not accepted."),
        ("submission_evidence", row.get("submission_evidence_status") in {"signed", "not_configured", "missing"}, "Submission Evidence Archive is not signed."),
        ("operations", row.get("operations_status") in {"signed", "force_signed", "not_configured", "missing"}, "Release Operations is not signed."),
    ]
    risks: list[dict[str, Any]] = []
    for domain, ok, message in checks:
        if ok:
            continue
        risks.append({"release_id": release_id, "domain": domain, "severity": "critical", "status": "open", "title": message, "public_safe_detail": message})
    return risks


def _has_blocking_delivery_status(row: ImplementationDocument) -> bool:
    return any(risk.get("severity") == "critical" for risk in _delivery_risks_for_row(row))


def _distribution_status(rows: list[ImplementationDocument]) -> str:
    if not rows:
        return "missing"
    if all(item.get("status") == "not_configured" for item in rows):
        return "not_configured"
    existing = [item for item in rows if item.get("target_id")]
    if not existing:
        return "missing"
    if any(item.get("verification_status") == "failed" for item in existing):
        return "failed"
    ready = [item for item in existing if item.get("signoff_status") in {"signed", "force_signed"} and item.get("verification_status") in {"passed", "warning"}]
    return "ready" if len(ready) == len(existing) else "partial" if ready else "missing"


def _submission_status(rows: list[ImplementationDocument]) -> str:
    if not rows:
        return "missing"
    if all(item.get("status") == "not_configured" for item in rows):
        return "not_configured"
    existing = [item for item in rows if item.get("submission_id")]
    if not existing:
        return "missing"
    if any(item.get("verification_status") == "failed" for item in existing):
        return "failed"
    if any(item.get("status") == "accepted" or int(item.get("accepted_count") or 0) > 0 for item in existing):
        return "accepted"
    if any(item.get("status") in {"submitted", "feedback_received", "needs_changes", "signed"} for item in existing):
        return "submitted"
    return "partial"


def _submission_evidence_status(rows: list[ImplementationDocument]) -> str:
    if not rows:
        return "missing"
    if all(item.get("status") == "not_configured" for item in rows):
        return "not_configured"
    existing = [item for item in rows if item.get("submission_id")]
    if not existing:
        return "missing"
    if any(item.get("verification_status") == "failed" or item.get("report_status") == "failed" for item in existing):
        return "failed"
    if any(item.get("signoff_status") in {"signed", "force_signed"} and item.get("verification_status") in {"passed", "warning"} for item in existing):
        return "signed"
    return "missing"


def _operations_status(rows: list[ImplementationDocument]) -> str:
    if not rows:
        return "missing"
    if all(item.get("status") == "not_configured" for item in rows):
        return "not_configured"
    first = rows[0]
    if first.get("operations_report_status") == "failed":
        return "failed"
    status = first.get("operations_signoff_status") or "missing"
    return status if status in {"signed", "force_signed"} else "unsigned" if first.get("operations_report_status") not in {"missing", None} else "missing"


def _operations_audit_status(rows: list[ImplementationDocument]) -> str:
    if not rows:
        return "missing"
    status = rows[0].get("operations_audit_status") or "missing"
    return status


def _operations_reviewer_pack_status(rows: list[ImplementationDocument]) -> str:
    if not rows:
        return "missing"
    status = rows[0].get("operations_reviewer_pack_status") or "missing"
    return status


def _package_status_from_fingerprints(packages: list[ImplementationDocument], package_type: str) -> str:
    matches = [item for item in packages if item.get("package_type") == package_type]
    if not matches:
        return "missing"
    return _aggregate_status([item.get("verification_status") for item in matches])


def _finding(check_id: str, severity: str, message: str) -> ImplementationDocument:
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


def _domain_from_summary(item: ImplementationDocument) -> str | None:
    if item.get("target_id") is not None:
        return "distribution"
    if item.get("submission_id") is not None and ("report_status" in item or "attachment_count" in item):
        return "submission_evidence"
    if item.get("submission_id") is not None:
        return "submission"
    if "operations_report_status" in item or "package_fingerprints" in item:
        return "operations"
    if "release_signoff_status" in item or "distribution_status" in item:
        return "release"
    return None





def _domain_not_configured_row(domain: str, release_id: str, **extra: Any) -> ImplementationDocument:
    row = {"release_id": release_id, "domain": domain, "status": "not_configured", "verification_status": "not_configured", **extra}
    row["fingerprint_hash"] = stable_hash(row)
    return row


def _latest_feedback_status(items: Any) -> str:
    statuses = [str(getattr(item, "status", "") or "") for item in items]
    if any(status == "accepted" for status in statuses):
        return "accepted"
    if any(status == "needs_changes" for status in statuses):
        return "needs_changes"
    if any(status == "feedback_received" for status in statuses):
        return "feedback_received"
    return "none"


def _nested_status(payload: ImplementationDocument, path: tuple[str, ...], *, default: str = "missing") -> str:
    value: Any = payload
    for part in path:
        if not isinstance(value, dict):
            return default
        value = value.get(part)
    return str(value or default)


def _stable_hash_without_zip(payload: ImplementationDocument) -> str | None:
    if not payload:
        return None
    return stable_hash({key: value for key, value in payload.items() if key != "zip"})


def _package_report_current_status(report: ImplementationDocument, zip_path: Path | None, manifest: ImplementationDocument) -> str:
    if not report:
        return "missing"
    if report.get("status") == "failed":
        return "failed"
    if zip_path is not None and zip_path.exists():
        current_sha = _sha256(zip_path)
        reported_sha = (report.get("input") if isinstance(report.get("input"), dict) else {}).get("sha256") or report.get("zip_sha256")
        if reported_sha and current_sha and str(reported_sha) != str(current_sha):
            return "stale"
        current_size = zip_path.stat().st_size
        reported_size = (report.get("input") if isinstance(report.get("input"), dict) else {}).get("size_bytes") or report.get("zip_size_bytes")
        if reported_size is not None and int(reported_size or 0) != int(current_size):
            return "stale"
    elif zip_path is not None:
        return "missing"
    manifest_hash = manifest.get("integrity_hash") or _stable_hash_without_zip(manifest)
    reported_manifest = report.get("manifest_hash")
    if reported_manifest and manifest_hash and str(reported_manifest) != str(manifest_hash):
        return "stale"
    status = str(report.get("status") or "missing")
    return status if status else "missing"


def _state_row(report: ImplementationDocument) -> dict[str, str]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {"source_hash": str(report.get("source_hash") or ""), "report_integrity_hash": str(report.get("integrity_hash") or ""), "public_package_count": str(summary.get("public_package_count") or 0)}


def _manifest_state(manifest: ImplementationDocument) -> dict[str, str]:
    return {"source_hash": str(manifest.get("source_hash") or ""), "report_integrity_hash": str((manifest.get("trust_center_report") if isinstance(manifest.get("trust_center_report"), dict) else {}).get("integrity_hash") or ""), "public_package_count": str(manifest.get("public_package_count") or 0)}


def _zip_manifest_state(zip_path: Path) -> dict[str, str]:
    manifest = _read_zip_json(zip_path, "trust-center-manifest.json")
    return _manifest_state(manifest)














def _page_record(root: Path, path: str, source_hash: Any) -> ImplementationDocument:
    resolved = root / path
    return {"path": path, "content_hash": _sha256(resolved), "source_hash": source_hash}


def _file_record(root: Path, path: Path) -> ImplementationDocument:
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


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return value if isinstance(value, dict) else dict(default or {})


def _read_zip_json(zip_path: Path, entry: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
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


def _verification_hash(report: ImplementationDocument) -> str | None:
    if not report:
        return None
    if report.get("schema_version") and "checks" in report:
        return ack_verification_hash(report)
    return stable_hash({key: value for key, value in report.items() if key != "generated_at"})


def _verification_current_status(report: ImplementationDocument, zip_sha256: Any, zip_size_bytes: Any, manifest_hash: Any) -> str:
    if not report:
        return "missing"
    status = str(report.get("status") or "missing")
    if status != "passed":
        return status
    if str(report.get("zip_sha256") or "") != str(zip_sha256 or ""):
        return "failed"
    if str(report.get("zip_size_bytes") or "") != str(zip_size_bytes or ""):
        return "failed"
    if str(report.get("manifest_hash") or "") != str(manifest_hash or ""):
        return "failed"
    return "passed"


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


def _redaction_summary(value: Any) -> ImplementationDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}


def _write_readme(export_dir: Path, report: ImplementationDocument) -> None:
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
