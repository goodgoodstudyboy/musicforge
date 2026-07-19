# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)
import hashlib as hashlib
import json as json
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Callable as Callable
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_contracts import PTC_BLOCKED_KEYS as PTC_BLOCKED_KEYS, PTC_HTML_PAGES as PTC_HTML_PAGES, PTC_PACKAGE_TYPE as PTC_PACKAGE_TYPE, expected_public_trust_center_documents as expected_public_trust_center_documents, public_trust_center_manifest_hash as public_trust_center_manifest_hash, public_trust_center_report_hash as public_trust_center_report_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash

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

MAX_TEXT_SCAN_BYTES = _make_deferred_global('MAX_TEXT_SCAN_BYTES')
VERIFIER_BLOCKED_KEYS = _make_deferred_global('VERIFIER_BLOCKED_KEYS')
_blocked_key_findings = _make_deferred_global('_blocked_key_findings')
_delivery_anchor_rows_from_fingerprint_sidecars = _make_deferred_global('_delivery_anchor_rows_from_fingerprint_sidecars')
_find_registry_current_entry = _make_deferred_global('_find_registry_current_entry')
_read_zip_json = _make_deferred_global('_read_zip_json')
_redaction_findings = _make_deferred_global('_redaction_findings')
doc = _make_deferred_global('doc')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
path = _make_deferred_global('path')

def bind_globals(namespace: dict[str, object]) -> None:
    global MAX_TEXT_SCAN_BYTES, VERIFIER_BLOCKED_KEYS, _blocked_key_findings, _delivery_anchor_rows_from_fingerprint_sidecars, _find_registry_current_entry, _read_zip_json, _redaction_findings
    global doc, item, key, path
    MAX_TEXT_SCAN_BYTES = namespace.get('MAX_TEXT_SCAN_BYTES', MAX_TEXT_SCAN_BYTES)
    VERIFIER_BLOCKED_KEYS = namespace.get('VERIFIER_BLOCKED_KEYS', VERIFIER_BLOCKED_KEYS)
    _blocked_key_findings = namespace.get('_blocked_key_findings', _blocked_key_findings)
    _delivery_anchor_rows_from_fingerprint_sidecars = namespace.get('_delivery_anchor_rows_from_fingerprint_sidecars', _delivery_anchor_rows_from_fingerprint_sidecars)
    _find_registry_current_entry = namespace.get('_find_registry_current_entry', _find_registry_current_entry)
    _read_zip_json = namespace.get('_read_zip_json', _read_zip_json)
    _redaction_findings = namespace.get('_redaction_findings', _redaction_findings)
    doc = namespace.get('doc', doc)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    path = namespace.get('path', path)
    _bind_deferred_defaults(namespace)


PTC_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 250
REQUIRED_ENTRIES = {
    "trust-center-manifest.json",
    "trust-center-report.json",
    "data/trust-center-data.json",
    "data/release-index.json",
    "data/portfolio-index.json",
    "data/package-index.json",
    "data/verification-index.json",
    "data/public-package-verification-index.json",
    "data/risk-register.json",
    "data/transparency-index.json",
    "data/acknowledgement-index.json",
    "data/delivery-index.json",
    "data/distribution-index.json",
    "data/submission-index.json",
    "data/submission-evidence-index.json",
    "data/operations-index.json",
    "data/operations-package-index.json",
    "data/readiness-matrix.json",
    "data/delivery-risk-register.json",
    "data/delivery-verification-index.json",
    "index.html",
    "releases.html",
    "portfolios.html",
    "delivery.html",
    "distribution.html",
    "submissions.html",
    "operations.html",
    "evidence.html",
    "risk.html",
    "verify.html",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"trust-center-manifest.json"}




class _PublicTrustCenterVerifierEvidenceMixin:
    def _verify_delivery_anchor(self) -> None:
        required = any(
            (
                self.require_delivery_readiness,
                self.require_distribution_ready,
                self.require_submission_accepted,
                self.require_submission_evidence,
                self.require_operations_signed,
                self.require_operations_audit,
                self.require_operations_reviewer_pack,
                self.anchor_registry_path is not None,
                self.anchor_transparency_path is not None,
                self.require_anchor_registry_current,
                self.require_anchor_transparency_current,
                self.require_anchor_checkpoint,
            )
        )
        if not required:
            return
        anchor_path = self.delivery_anchor_path or self.zip_path.with_name(self.zip_path.stem + ".delivery-anchor.json")
        if not anchor_path.exists() or not anchor_path.is_file() or anchor_path.is_symlink():
            self._add_check("requirements", "ptc_delivery_external_anchor", "failed", "blocking", "Delivery verification requires an external Public Trust Center delivery anchor.")
            return
        try:
            anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._add_check("requirements", "ptc_delivery_external_anchor", "failed", "blocking", f"Delivery anchor cannot be read: {exc}")
            return
        self.delivery_anchor_doc = _as_document(anchor)
        self._add_exact_check("requirements", "ptc_delivery_anchor_package_type", self.delivery_anchor_doc.get("package_type"), "musicforge_public_trust_center_delivery_anchor", "Delivery anchor package type")
        self._add_exact_check("requirements", "ptc_delivery_anchor_hash", self.delivery_anchor_doc.get("anchor_hash"), stable_hash({key: value for key, value in self.delivery_anchor_doc.items() if key != "anchor_hash"}), "Delivery anchor integrity")
        self._add_exact_check("requirements", "ptc_delivery_anchor_zip_sha256", self.delivery_anchor_doc.get("zip_sha256"), self.zip_sha256, "Delivery anchor ZIP sha256")
        self._add_exact_check("requirements", "ptc_delivery_anchor_zip_size", self.delivery_anchor_doc.get("zip_size_bytes"), self.zip_size_bytes, "Delivery anchor ZIP size")
        self._add_exact_check("requirements", "ptc_delivery_anchor_manifest_hash", self.delivery_anchor_doc.get("manifest_hash"), self.manifest.get("integrity_hash"), "Delivery anchor manifest hash")
        self._add_exact_check("requirements", "ptc_delivery_anchor_source_hash", self.delivery_anchor_doc.get("source_hash"), self.report_doc.get("source_hash"), "Delivery anchor source hash")
        expected = _delivery_anchor_rows_from_fingerprint_sidecars({name: doc for name, doc in self.data_docs.items() if name.startswith("delivery-fingerprint-summaries/")})
        actual = _as_list(self.delivery_anchor_doc.get("fingerprint_sidecars"))
        self._add_exact_check("requirements", "ptc_delivery_anchor_fingerprint_sidecars", actual, expected, "Delivery anchor binds fingerprint sidecars")

    def _verify_anchor_registry(self) -> None:
        required = self.require_anchor_registry_current or self.require_anchor_published or self.require_anchor_not_revoked or self.anchor_registry_path is not None
        if not required:
            return
        registry_path = self.anchor_registry_path
        if registry_path is None:
            self._add_check("requirements", "ptc_anchor_registry_present", "failed", "blocking", "Anchor Registry ZIP is required.")
            return
        if not registry_path.exists() or not registry_path.is_file() or registry_path.is_symlink():
            self._add_check("requirements", "ptc_anchor_registry_present", "failed", "blocking", "Anchor Registry ZIP does not exist or is not a regular file.")
            return
        try:
            from song_agent.domains.trust.public_trust_center_anchor_registry_verifier import verify_public_trust_center_anchor_registry_package
        except Exception as exc:
            self._add_check("requirements", "ptc_anchor_registry_import", "failed", "blocking", f"Anchor Registry verifier cannot be imported: {exc}")
            return
        registry_report = verify_public_trust_center_anchor_registry_package(
            registry_path,
            strict=self.strict,
            require_current=self.require_anchor_registry_current,
            require_anchor_published=self.require_anchor_published,
            require_anchor_not_revoked=self.require_anchor_not_revoked,
            max_zip_size_mb=self.max_zip_size_mb,
            max_uncompressed_size_mb=self.max_uncompressed_size_mb,
            max_entry_count=self.max_entry_count,
            now=self.generated_at,
        )
        self.anchor_registry_verification = registry_report
        self._add_exact_check("requirements", "ptc_anchor_registry_verification_status", registry_report.get("status"), "passed", "Anchor Registry verification status")
        registry = _read_zip_json(registry_path, "registry.json")
        current = _find_registry_current_entry(registry)
        registry_anchor = current.get("anchor") if current and isinstance(current.get("anchor"), dict) else {}
        self._add_exact_check("requirements", "ptc_anchor_registry_current_anchor", registry_anchor, self.delivery_anchor_doc, "Anchor Registry current anchor matches delivery anchor")
        self._add_exact_check("requirements", "ptc_anchor_registry_zip_sha256", _as_document(registry_anchor).get("zip_sha256"), self.zip_sha256, "Anchor Registry current anchor ZIP sha256")
        self._add_exact_check("requirements", "ptc_anchor_registry_manifest_hash", _as_document(registry_anchor).get("manifest_hash"), self.manifest.get("integrity_hash"), "Anchor Registry current anchor manifest hash")
        self._add_exact_check("requirements", "ptc_anchor_registry_source_hash", _as_document(registry_anchor).get("source_hash"), self.report_doc.get("source_hash"), "Anchor Registry current anchor source hash")
        if self.require_anchor_published or self.require_anchor_registry_current:
            self._add_exact_check("requirements", "ptc_anchor_registry_current_status", current.get("status") if current else None, "published", "Anchor Registry current entry status")
        if self.require_anchor_not_revoked:
            ok = bool(current) and current.get("status") != "revoked"
            self._add_check("requirements", "ptc_anchor_registry_not_revoked", "passed" if ok else "failed", "blocking", "Anchor Registry current entry is not revoked." if ok else "Anchor Registry current entry is revoked or missing.")

    def _verify_anchor_transparency(self) -> None:
        required = self.require_anchor_transparency_current or self.require_anchor_checkpoint or self.anchor_transparency_path is not None or self.anchor_checkpoint_path is not None
        if not required:
            return
        if self.anchor_transparency_path is None:
            self._add_check("requirements", "ptc_anchor_transparency_present", "failed", "blocking", "Anchor Transparency ZIP is required.")
            return
        if not self.anchor_transparency_path.exists() or not self.anchor_transparency_path.is_file() or self.anchor_transparency_path.is_symlink():
            self._add_check("requirements", "ptc_anchor_transparency_present", "failed", "blocking", "Anchor Transparency ZIP does not exist or is not a regular file.")
            return
        if self.require_anchor_checkpoint and self.anchor_checkpoint_path is None:
            self._add_check("requirements", "ptc_anchor_checkpoint_present", "failed", "blocking", "External anchor checkpoint is required.")
            return
        try:
            from song_agent.domains.trust.public_trust_center_anchor_transparency_verifier import verify_public_trust_center_anchor_transparency_package
        except Exception as exc:
            self._add_check("requirements", "ptc_anchor_transparency_import", "failed", "blocking", f"Anchor Transparency verifier cannot be imported: {exc}")
            return
        transparency_report = verify_public_trust_center_anchor_transparency_package(
            self.anchor_transparency_path,
            strict=self.strict,
            checkpoint_path=self.anchor_checkpoint_path,
            anchor_registry_path=self.anchor_registry_path,
            require_current_checkpoint=self.require_anchor_transparency_current or self.require_anchor_checkpoint,
            require_published_anchor=self.require_anchor_published or self.require_anchor_registry_current,
            require_not_revoked=self.require_anchor_not_revoked,
            max_zip_size_mb=self.max_zip_size_mb,
            max_uncompressed_size_mb=self.max_uncompressed_size_mb,
            max_entry_count=self.max_entry_count,
            now=self.generated_at,
        )
        self.anchor_transparency_verification = transparency_report
        self._add_exact_check("requirements", "ptc_anchor_transparency_verification_status", transparency_report.get("status"), "passed", "Anchor Transparency verification status")
        source = _read_zip_json(self.anchor_transparency_path, "anchor-transparency-report.json").get("source", {})
        if not isinstance(source, dict):
            source = {}
        self._add_hash_check("requirements", "ptc_anchor_transparency_ptc_zip_sha256", source.get("ptc_zip_sha256"), self.zip_sha256, "Anchor Transparency PTC ZIP sha256")
        self._add_hash_check("requirements", "ptc_anchor_transparency_ptc_manifest_hash", source.get("ptc_manifest_hash"), self.manifest.get("integrity_hash"), "Anchor Transparency PTC manifest hash")
        self._add_hash_check("requirements", "ptc_anchor_transparency_ptc_source_hash", source.get("ptc_source_hash"), self.report_doc.get("source_hash"), "Anchor Transparency PTC source hash")
        if self.delivery_anchor_doc:
            self._add_hash_check("requirements", "ptc_anchor_transparency_anchor_hash", source.get("current_anchor_hash"), self.delivery_anchor_doc.get("anchor_hash"), "Anchor Transparency current anchor hash")
        if self.anchor_registry_verification:
            self._add_hash_check("requirements", "ptc_anchor_transparency_registry_zip_sha256", source.get("registry_zip_sha256"), self.anchor_registry_verification.get("zip_sha256"), "Anchor Transparency Anchor Registry ZIP sha256")
            self._add_hash_check("requirements", "ptc_anchor_transparency_registry_manifest_hash", source.get("registry_manifest_hash"), self.anchor_registry_verification.get("manifest_hash"), "Anchor Transparency Anchor Registry manifest hash")
        if self.require_anchor_transparency_current:
            checkpoint_hash = transparency_report.get("checkpoint_hash")
            self._add_check("requirements", "ptc_anchor_transparency_checkpoint_current", "passed" if checkpoint_hash else "failed", "blocking", "Anchor Transparency current checkpoint is present." if checkpoint_hash else "Anchor Transparency current checkpoint is required.")

    def _verify_acceptance_board_signoff(self) -> None:
        required = self.require_acceptance_board_signoff or self.acceptance_board_signoff_archive_path is not None
        if not required:
            return
        if self.acceptance_board_signoff_archive_path is None:
            self._add_check("requirements", "ptc_require_acceptance_board_signoff", "failed", "blocking", "Acceptance Board signoff archive is required.")
            return
        if not self.acceptance_board_signoff_archive_path.exists() or not self.acceptance_board_signoff_archive_path.is_file() or self.acceptance_board_signoff_archive_path.is_symlink():
            self._add_check("requirements", "ptc_acceptance_board_signoff_archive_present", "failed", "blocking", "Acceptance Board signoff archive ZIP does not exist or is not a regular file.")
            return
        missing_current_evidence = [
            name
            for name, path in [
                ("acceptance_board", self.acceptance_board_path),
                ("acceptance_board_verification_report", self.acceptance_board_verification_report_path),
                ("distribution_kit", self.distribution_kit_path),
                ("accepted_evidence_dir", self.accepted_evidence_dir),
            ]
            if path is None
        ]
        self._add_check(
            "requirements",
            "ptc_acceptance_board_signoff_current_evidence_required",
            "failed" if missing_current_evidence else "passed",
            "blocking",
            "Acceptance Board signoff current evidence is complete."
            if not missing_current_evidence
            else "Acceptance Board signoff current evidence is missing: " + ", ".join(missing_current_evidence) + ".",
        )
        if self.acceptance_board_signoff_verifier is None:
            self._add_check("requirements", "ptc_acceptance_board_signoff_import", "failed", "blocking", "Acceptance Board signoff verifier is not configured.")
            return
        report = self.acceptance_board_signoff_verifier(
            self.acceptance_board_signoff_archive_path,
            strict=True,
            require_signed=True,
            require_current=True,
            require_ready=True,
            board_zip_path=self.acceptance_board_path,
            board_verification_report_path=self.acceptance_board_verification_report_path,
            distribution_kit_path=self.distribution_kit_path,
            accepted_evidence_dir=self.accepted_evidence_dir,
            now=self.generated_at,
        )
        self._add_exact_check("requirements", "ptc_acceptance_board_signoff_verification_status", report.get("status"), "passed", "Acceptance Board signoff archive verification status")
        summary = _as_document(report.get("summary"))
        self._add_exact_check("requirements", "ptc_acceptance_board_signoff_status", summary.get("signoff_status"), "signed", "Acceptance Board signoff status")
        self._add_exact_check("requirements", "ptc_acceptance_board_signoff_ready", summary.get("board_readiness"), "ready", "Acceptance Board readiness")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.endswith((".json", ".txt", ".md", ".html")):
                continue
            info = self.entry_map.get(name)
            if info is None or info.file_size > MAX_TEXT_SCAN_BYTES:
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except (OSError, UnicodeDecodeError, RuntimeError):
                continue
            self.redaction_findings.extend(_redaction_findings(name, text))
            if name.endswith(".json"):
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    continue
                self.redaction_findings.extend(_blocked_key_findings(name, value))
        self._add_check("redaction", "ptc_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> DomainDocument:
        info = self.entry_map.get(name)
        if not name or info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name or 'entry'} is missing.")
            return {}
        try:
            value = json.loads(archive.read(info).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be parsed: {exc}")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parses as JSON.")
        return _as_document(value)

    def _build_report(self) -> DomainDocument:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = _as_document(self.report_doc.get("summary"))
        summary = dict(summary)
        summary.update({"center_id": self.manifest.get("center_id") or self.report_doc.get("center_id"), "blocker_count": len(blockers), "warning_count": len(warnings)})
        report = {
            "schema_version": PTC_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
            "summary": summary,
            "checks": self.checks,
            "files": self.files,
            "blockers": blockers,
            "warnings": warnings,
            "redaction_findings": self.redaction_findings[:50],
        }
        return sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _add_hash_check(self, scope: str, check_id: str, expected: object, actual: object, label: str) -> None:
        ok = bool(expected) and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_exact_check(self, scope: str, check_id: str, expected: object, actual: object, label: str) -> None:
        ok = expected == actual
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})
