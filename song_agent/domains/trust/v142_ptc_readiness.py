# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
import html as html
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
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model import accepted_evidence_verification_summary_from_portfolio_dir as accepted_evidence_verification_summary_from_portfolio_dir
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal as verify_release_portfolio_governance_attestation_portal
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry as verify_release_portfolio_governance_attestation_registry
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore as ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore, verification_hash as ack_verification_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import verify_release_portfolio_governance_attestation_transparency_acknowledgement_package as verify_release_portfolio_governance_attestation_transparency_acknowledgement_package
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_verifier import verify_release_portfolio_governance_attestation_transparency as verify_release_portfolio_governance_attestation_transparency
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_contracts import PTC_BLOCKED_KEYS as PTC_BLOCKED_KEYS, PTC_HTML_PAGES as PTC_HTML_PAGES, PTC_MANIFEST_HASH_EXCLUDE_KEYS as PTC_MANIFEST_HASH_EXCLUDE_KEYS, PTC_PACKAGE_TYPE as PTC_PACKAGE_TYPE, PTC_REPORT_HASH_EXCLUDE_KEYS as PTC_REPORT_HASH_EXCLUDE_KEYS, _DELIVERY_COLLECTION_DOMAINS as _DELIVERY_COLLECTION_DOMAINS, _delivery_item_status as _delivery_item_status, _delivery_public_payload as _delivery_public_payload, _delivery_summary_from_item as _delivery_summary_from_item, _delivery_summary_key as _delivery_summary_key, _delivery_verification_index_from_sidecars as _delivery_verification_index_from_sidecars, _delivery_verification_index_from_source as _delivery_verification_index_from_source, _fingerprint_key as _fingerprint_key, _html_shell as _html_shell, _kv as _kv, _links as _links, _package_index as _package_index, _package_verification_index_from_sidecars as _package_verification_index_from_sidecars, _package_verification_sidecars as _package_verification_sidecars, _table as _table, _verification_index as _verification_index, _verification_sidecars as _verification_sidecars, _verification_sidecars_from_docs as _verification_sidecars_from_docs, expected_public_trust_center_documents as expected_public_trust_center_documents, public_trust_center_data_documents as public_trust_center_data_documents, public_trust_center_html_pages as public_trust_center_html_pages, public_trust_center_manifest_hash as public_trust_center_manifest_hash, public_trust_center_report_hash as public_trust_center_report_hash

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

PublicTrustCenterNotFoundError = _make_deferred_global('PublicTrustCenterNotFoundError')
PublicTrustCenterStateError = _make_deferred_global('PublicTrustCenterStateError')
_delivery_readiness = _make_deferred_global('_delivery_readiness')
_delivery_readiness_matrix_from_parts = _make_deferred_global('_delivery_readiness_matrix_from_parts')
_delivery_risk_register = _make_deferred_global('_delivery_risk_register')
_delivery_risk_register_from_matrix = _make_deferred_global('_delivery_risk_register_from_matrix')
_ensure_within = _make_deferred_global('_ensure_within')
_file_record = _make_deferred_global('_file_record')
_findings_from_source = _make_deferred_global('_findings_from_source')
_manifest_state = _make_deferred_global('_manifest_state')
_normalize_policy = _make_deferred_global('_normalize_policy')
_normalize_selection = _make_deferred_global('_normalize_selection')
_page_record = _make_deferred_global('_page_record')
_portfolio_readiness = _make_deferred_global('_portfolio_readiness')
_read_json_default = _make_deferred_global('_read_json_default')
_release_readiness = _make_deferred_global('_release_readiness')
_risk_register = _make_deferred_global('_risk_register')
_safe_id = _make_deferred_global('_safe_id')
_sanitize_public_metadata = _make_deferred_global('_sanitize_public_metadata')
_sha256 = _make_deferred_global('_sha256')
_state_row = _make_deferred_global('_state_row')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
_zip_manifest_state = _make_deferred_global('_zip_manifest_state')
key = _make_deferred_global('key')
pkg = _make_deferred_global('pkg')
public_trust_center_config_hash = _make_deferred_global('public_trust_center_config_hash')
public_trust_center_config_summary = _make_deferred_global('public_trust_center_config_summary')
public_trust_center_summary = _make_deferred_global('public_trust_center_summary')
public_trust_center_summary_from_source = _make_deferred_global('public_trust_center_summary_from_source')
row = _make_deferred_global('row')
ver = _make_deferred_global('ver')

def bind_globals(namespace: dict[str, object]) -> None:
    global PublicTrustCenterNotFoundError, PublicTrustCenterStateError, _delivery_readiness, _delivery_readiness_matrix_from_parts, _delivery_risk_register, _delivery_risk_register_from_matrix, _ensure_within, _file_record
    global _findings_from_source, _manifest_state, _normalize_policy, _normalize_selection, _page_record, _portfolio_readiness, _read_json_default
    global _release_readiness, _risk_register, _safe_id, _sanitize_public_metadata, _sha256, _state_row, _write_json, _write_readme
    global _write_zip, _zip_entries, _zip_manifest_state, key, pkg, public_trust_center_config_hash, public_trust_center_config_summary, public_trust_center_summary
    global public_trust_center_summary_from_source, row, ver
    PublicTrustCenterNotFoundError = namespace.get('PublicTrustCenterNotFoundError', PublicTrustCenterNotFoundError)
    PublicTrustCenterStateError = namespace.get('PublicTrustCenterStateError', PublicTrustCenterStateError)
    _delivery_readiness = namespace.get('_delivery_readiness', _delivery_readiness)
    _delivery_readiness_matrix_from_parts = namespace.get('_delivery_readiness_matrix_from_parts', _delivery_readiness_matrix_from_parts)
    _delivery_risk_register = namespace.get('_delivery_risk_register', _delivery_risk_register)
    _delivery_risk_register_from_matrix = namespace.get('_delivery_risk_register_from_matrix', _delivery_risk_register_from_matrix)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _file_record = namespace.get('_file_record', _file_record)
    _findings_from_source = namespace.get('_findings_from_source', _findings_from_source)
    _manifest_state = namespace.get('_manifest_state', _manifest_state)
    _normalize_policy = namespace.get('_normalize_policy', _normalize_policy)
    _normalize_selection = namespace.get('_normalize_selection', _normalize_selection)
    _page_record = namespace.get('_page_record', _page_record)
    _portfolio_readiness = namespace.get('_portfolio_readiness', _portfolio_readiness)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _release_readiness = namespace.get('_release_readiness', _release_readiness)
    _risk_register = namespace.get('_risk_register', _risk_register)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize_public_metadata = namespace.get('_sanitize_public_metadata', _sanitize_public_metadata)
    _sha256 = namespace.get('_sha256', _sha256)
    _state_row = namespace.get('_state_row', _state_row)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    _zip_manifest_state = namespace.get('_zip_manifest_state', _zip_manifest_state)
    key = namespace.get('key', key)
    pkg = namespace.get('pkg', pkg)
    public_trust_center_config_hash = namespace.get('public_trust_center_config_hash', public_trust_center_config_hash)
    public_trust_center_config_summary = namespace.get('public_trust_center_config_summary', public_trust_center_config_summary)
    public_trust_center_summary = namespace.get('public_trust_center_summary', public_trust_center_summary)
    public_trust_center_summary_from_source = namespace.get('public_trust_center_summary_from_source', public_trust_center_summary_from_source)
    row = namespace.get('row', row)
    ver = namespace.get('ver', ver)
    _bind_deferred_defaults(namespace)


PTC_SCHEMA_VERSION = 1
PTC_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_report"
PTC_CONFIG_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
PTC_DELIVERY_DOMAINS = ("release", "distribution", "submission", "submission_evidence", "operations", "operations_audit", "operations_reviewer_pack")




class PublicTrustCenterStoreReadinessMixin:
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

    def list_centers(self) -> list[DomainDocument]:
        if not self.root.exists():
            return []
        rows: list[DomainDocument] = []
        for path in sorted(self.root.iterdir()):
            if not path.is_dir():
                continue
            config = _read_json_default(path / "trust-center.json", default={})
            report = _read_json_default(path / "trust-center-report.json", default={})
            if config:
                rows.append({"center": public_trust_center_config_summary(config), "summary": public_trust_center_summary(report) if report else {"status": "missing"}})
        return rows

    def read_config(self, center_id: str = "ptc-default", *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.config_path(center_id), default=default)

    def read_report(self, center_id: str = "ptc-default", *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.report_path(center_id), default=default)

    def read_export_manifest(self, center_id: str = "ptc-default") -> DomainDocument:
        path = self.export_dir(center_id) / "trust-center-manifest.json"
        if not path.exists():
            raise PublicTrustCenterNotFoundError("Public Trust Center export has not been generated.")
        value = read_json(path)
        return _as_document(value)

    def create_or_update_center(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            center_id = _safe_id(str(payload.get("center_id") or payload.get("id") or "ptc-default"))
            existing = self.read_config(center_id, default={})
            selection = _normalize_selection(_document_or(payload.get("selection"), payload))
            policy = _normalize_policy(_document_or(payload.get("policy"), payload))
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

    def get_center(self, center_id: str = "ptc-default") -> DomainDocument:
        config = self.read_config(center_id, default={})
        if not config:
            raise PublicTrustCenterNotFoundError(f"Public Trust Center not found: {center_id}")
        report = self.read_report(center_id, default={})
        summary: DomainDocument = public_trust_center_summary(report) if report else {"status": "missing", "center_id": center_id}
        if report:
            summary["stale"] = self.report_is_stale(center_id, report)
        return {"config": config, "report": report, "summary": summary}

    def build_source(self, center_id: str = "ptc-default") -> DomainDocument:
        config = self.read_config(center_id, default={}) or self.create_or_update_center({"center_id": center_id})
        selection = _as_document(config.get("selection"))
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
            "policy": _as_document(config.get("policy")),
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

    def refresh_report(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def report_is_stale(self, center_id: str = "ptc-default", report: DomainDocument | None = None) -> bool:
        data = _document_or(report, self.read_report(center_id, default={}))
        if not data:
            return False
        try:
            source = self.build_source(center_id)
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_center(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def build_zip(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def verify_zip(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def archive_snapshot(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def _write_delivery_anchor(self, center_id: str, manifest: DomainDocument, zip_info: DomainDocument) -> DomainDocument:
        export_dir = self.export_dir(center_id)
        rows: list[DomainDocument] = []
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
                    "fingerprints_hash": stable_hash(_as_document(doc.get("fingerprints"))),
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

    def _release_summaries(self, selection: DomainDocument) -> list[DomainDocument]:
        ids = [str(item).strip() for item in selection.get("release_ids", []) if str(item).strip()] if isinstance(selection.get("release_ids"), list) else []
        if not ids and bool(selection.get("include_all_releases", True)):
            try:
                ids = [item.release_id for item in self.release_store.list_releases(include_hidden=False)]
            except Exception:
                ids = []
        rows: list[DomainDocument] = []
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

    def _delivery_bundle(self, selection: DomainDocument, releases: list[DomainDocument], portfolios: list[DomainDocument]) -> DomainDocument:
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
