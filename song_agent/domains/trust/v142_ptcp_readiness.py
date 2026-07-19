# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
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
from song_agent.domains.trust.public_trust_center import PublicTrustCenterStore as PublicTrustCenterStore
from song_agent.domains.trust.public_trust_center_acceptance_board import PublicTrustCenterAcceptanceBoardStore as PublicTrustCenterAcceptanceBoardStore
from song_agent.domains.trust.public_trust_center_acceptance_board import acceptance_board_verification_hash as acceptance_board_verification_hash
from song_agent.domains.trust.public_trust_center_acceptance_board_signoff_verifier import verify_public_trust_center_acceptance_board_signoff_archive_package as verify_public_trust_center_acceptance_board_signoff_archive_package, write_public_trust_center_acceptance_board_signoff_archive_verification_report as write_public_trust_center_acceptance_board_signoff_archive_verification_report
from song_agent.domains.trust.public_trust_center_acceptance_board_verifier import verify_public_trust_center_acceptance_board_package as verify_public_trust_center_acceptance_board_package
from song_agent.domains.trust.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore as PublicTrustCenterAnchorRegistryStore
from song_agent.domains.trust.public_trust_center_anchor_registry_verifier import verify_public_trust_center_anchor_registry_package as verify_public_trust_center_anchor_registry_package, write_public_trust_center_anchor_registry_verification_report as write_public_trust_center_anchor_registry_verification_report
from song_agent.domains.trust.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore as PublicTrustCenterAnchorTransparencyStore
from song_agent.domains.trust.public_trust_center_anchor_transparency_verifier import verify_public_trust_center_anchor_transparency_package as verify_public_trust_center_anchor_transparency_package, write_public_trust_center_anchor_transparency_verification_report as write_public_trust_center_anchor_transparency_verification_report
from song_agent.domains.trust.public_trust_center_distribution_kit import PublicTrustCenterDistributionKitStore as PublicTrustCenterDistributionKitStore
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance import PublicTrustCenterDistributionKitAcceptanceStore as PublicTrustCenterDistributionKitAcceptanceStore, verification_hash as accepted_evidence_verification_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package as verify_public_trust_center_distribution_kit_accepted_evidence_package, write_public_trust_center_distribution_kit_accepted_evidence_verification_report as write_public_trust_center_distribution_kit_accepted_evidence_verification_report
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package, write_public_trust_center_distribution_kit_verification_report as write_public_trust_center_distribution_kit_verification_report
from song_agent.domains.trust.public_trust_center_verifier import verify_public_trust_center_package as verify_public_trust_center_package, write_public_trust_center_verification_report as write_public_trust_center_verification_report
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_publication_contracts import PUBLICATION_BLOCKED_KEYS as PUBLICATION_BLOCKED_KEYS, PUBLICATION_CHANNEL_STATE_HASH_EXCLUDE_KEYS as PUBLICATION_CHANNEL_STATE_HASH_EXCLUDE_KEYS, PUBLICATION_CHANNEL_STATE_PACKAGE_TYPE as PUBLICATION_CHANNEL_STATE_PACKAGE_TYPE, PUBLICATION_MANIFEST_HASH_EXCLUDE_KEYS as PUBLICATION_MANIFEST_HASH_EXCLUDE_KEYS, PUBLICATION_PACKAGE_TYPE as PUBLICATION_PACKAGE_TYPE, PUBLICATION_REPORT_HASH_EXCLUDE_KEYS as PUBLICATION_REPORT_HASH_EXCLUDE_KEYS, PUBLICATION_REQUIRED_PACKAGE_KEYS as PUBLICATION_REQUIRED_PACKAGE_KEYS, PUBLICATION_SIDECAR_HASH_EXCLUDE_KEYS as PUBLICATION_SIDECAR_HASH_EXCLUDE_KEYS, publication_channel_state_hash as publication_channel_state_hash, publication_manifest_hash as publication_manifest_hash, publication_report_hash as publication_report_hash, sidecar_hash as sidecar_hash

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

PublicTrustCenterPublicationNotFoundError = _make_deferred_global('PublicTrustCenterPublicationNotFoundError')
PublicTrustCenterPublicationStateError = _make_deferred_global('PublicTrustCenterPublicationStateError')
_accepted_package_rows = _make_deferred_global('_accepted_package_rows')
_accepted_verification_rows = _make_deferred_global('_accepted_verification_rows')
_checksum_json = _make_deferred_global('_checksum_json')
_default_policy = _make_deferred_global('_default_policy')
_ensure_within = _make_deferred_global('_ensure_within')
_file_record = _make_deferred_global('_file_record')
_fs_path = _make_deferred_global('_fs_path')
_next_channel_id = _make_deferred_global('_next_channel_id')
_next_publication_id = _make_deferred_global('_next_publication_id')
_package_row = _make_deferred_global('_package_row')
_path_for_package = _make_deferred_global('_path_for_package')
_path_for_verification = _make_deferred_global('_path_for_verification')
_read_json_default = _make_deferred_global('_read_json_default')
_read_zip_json = _make_deferred_global('_read_zip_json')
_safe_copy = _make_deferred_global('_safe_copy')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
_sha256 = _make_deferred_global('_sha256')
_verification_hash = _make_deferred_global('_verification_hash')
_verification_row = _make_deferred_global('_verification_row')
_walk_files = _make_deferred_global('_walk_files')
_write_html_pages = _make_deferred_global('_write_html_pages')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_write_sha256sums = _make_deferred_global('_write_sha256sums')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
entry = _make_deferred_global('entry')
key = _make_deferred_global('key')
publication_channel_hash = _make_deferred_global('publication_channel_hash')

def bind_globals(namespace: dict[str, object]) -> None:
    global PublicTrustCenterPublicationNotFoundError, PublicTrustCenterPublicationStateError, _accepted_package_rows, _accepted_verification_rows, _checksum_json, _default_policy, _ensure_within, _file_record
    global _fs_path, _next_channel_id, _next_publication_id, _package_row, _path_for_package, _path_for_verification, _read_json_default
    global _read_zip_json, _safe_copy, _safe_id, _sanitize, _sha256, _verification_hash, _verification_row, _walk_files
    global _write_html_pages, _write_json, _write_readme, _write_sha256sums, _write_zip, _zip_entries, entry, key
    global publication_channel_hash
    PublicTrustCenterPublicationNotFoundError = namespace.get('PublicTrustCenterPublicationNotFoundError', PublicTrustCenterPublicationNotFoundError)
    PublicTrustCenterPublicationStateError = namespace.get('PublicTrustCenterPublicationStateError', PublicTrustCenterPublicationStateError)
    _accepted_package_rows = namespace.get('_accepted_package_rows', _accepted_package_rows)
    _accepted_verification_rows = namespace.get('_accepted_verification_rows', _accepted_verification_rows)
    _checksum_json = namespace.get('_checksum_json', _checksum_json)
    _default_policy = namespace.get('_default_policy', _default_policy)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _file_record = namespace.get('_file_record', _file_record)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _next_channel_id = namespace.get('_next_channel_id', _next_channel_id)
    _next_publication_id = namespace.get('_next_publication_id', _next_publication_id)
    _package_row = namespace.get('_package_row', _package_row)
    _path_for_package = namespace.get('_path_for_package', _path_for_package)
    _path_for_verification = namespace.get('_path_for_verification', _path_for_verification)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_zip_json = namespace.get('_read_zip_json', _read_zip_json)
    _safe_copy = namespace.get('_safe_copy', _safe_copy)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _sha256 = namespace.get('_sha256', _sha256)
    _verification_hash = namespace.get('_verification_hash', _verification_hash)
    _verification_row = namespace.get('_verification_row', _verification_row)
    _walk_files = namespace.get('_walk_files', _walk_files)
    _write_html_pages = namespace.get('_write_html_pages', _write_html_pages)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _write_sha256sums = namespace.get('_write_sha256sums', _write_sha256sums)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    entry = namespace.get('entry', entry)
    key = namespace.get('key', key)
    publication_channel_hash = namespace.get('publication_channel_hash', publication_channel_hash)
    _bind_deferred_defaults(namespace)


PUBLICATION_SCHEMA_VERSION = 1
PUBLICATION_CHANNEL_PACKAGE_TYPE = "musicforge_public_trust_center_publication_channel"
PUBLICATION_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_publication_report"
PUBLICATION_CHANNEL_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
PUBLICATION_ALLOWED_CHANNEL_TYPES = {"internal_preview", "partner_handoff", "public_release", "archive_mirror"}




class PublicTrustCenterPublicationStoreReadinessMixin:
    def root_dir(self, center_id: str = "ptc-default") -> Path:
        return self.trust_center_store.center_dir(center_id) / "publications"

    def channels_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "channels"

    def channel_dir(self, center_id: str, channel_id: str) -> Path:
        return self.channels_dir(center_id) / _safe_id(channel_id)

    def channel_path(self, center_id: str, channel_id: str) -> Path:
        return self.channel_dir(center_id, channel_id) / "channel.json"

    def events_path(self, center_id: str, channel_id: str) -> Path:
        return self.channel_dir(center_id, channel_id) / "events.jsonl"

    def current_publication_path(self, center_id: str, channel_id: str) -> Path:
        return self.channel_dir(center_id, channel_id) / "current-publication.json"

    def channel_state_path(self, center_id: str, channel_id: str) -> Path:
        return self.channel_dir(center_id, channel_id) / "publication-channel-state.json"

    def snapshots_dir(self, center_id: str, channel_id: str) -> Path:
        return self.channel_dir(center_id, channel_id) / "snapshots"

    def snapshot_dir(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshots_dir(center_id, channel_id) / _safe_id(publication_id)

    def report_path(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshot_dir(center_id, channel_id, publication_id) / "publication-report.json"

    def export_dir(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshot_dir(center_id, channel_id, publication_id) / "export"

    def zip_path(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshot_dir(center_id, channel_id, publication_id) / "public-trust-center-publication.zip"

    def verification_report_path(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshot_dir(center_id, channel_id, publication_id) / "publication-verification-report.json"

    def mirror_verification_report_path(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshot_dir(center_id, channel_id, publication_id) / "publication-mirror-verification-report.json"

    def create_channel(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            channel_id = _safe_id(str(payload.get("channel_id") or _next_channel_id(self.channels_dir(center_id))))
            channel_type = str(payload.get("channel_type") or "public_release")
            if channel_type not in PUBLICATION_ALLOWED_CHANNEL_TYPES:
                raise PublicTrustCenterPublicationStateError("Invalid Public Trust Center publication channel_type.")
            policy = _default_policy(channel_type)
            if isinstance(payload.get("policy"), dict):
                policy.update({key: bool(value) for key, value in payload["policy"].items() if key in policy})
            channel = {
                "schema_version": PUBLICATION_SCHEMA_VERSION,
                "package_type": PUBLICATION_CHANNEL_PACKAGE_TYPE,
                "channel_id": channel_id,
                "center_id": center_id,
                "name": sanitize_sensitive_text(str(payload.get("name") or "Public Trust Center Release Channel")[:160]),
                "channel_type": channel_type,
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "description": sanitize_sensitive_text(str(payload.get("description") or "")[:1000]),
                "policy": policy,
                "site_options": {
                    "include_html": bool((_as_document(payload.get("site_options"))).get("include_html", True)),
                    "include_checksums": True,
                    "include_readme": True,
                    "include_verification_commands": True,
                },
            }
            channel["integrity_hash"] = publication_channel_hash(channel)
            self.channel_dir(center_id, channel_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.channel_path(center_id, channel_id), channel)
            self._append_event(center_id, channel_id, "channel_created", {"channel_hash": channel["integrity_hash"]}, now=now)
            return _sanitize(channel)

    def read_channel(self, center_id: str, channel_id: str) -> DomainDocument:
        value = _read_json_default(self.channel_path(center_id, channel_id), default={})
        if not value:
            raise PublicTrustCenterPublicationNotFoundError("Public Trust Center publication channel not found.")
        return value

    def list_channels(self, center_id: str | None = None, include_inactive: bool = False) -> list[DomainDocument]:
        roots = [self.channels_dir(center_id)] if center_id else sorted(path / "publications" / "channels" for path in self.trust_center_store.root.glob("*") if path.is_dir())
        rows: list[DomainDocument] = []
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.glob("*/channel.json")):
                channel = _read_json_default(path, default={})
                if not channel:
                    continue
                if not include_inactive and channel.get("status") != "active":
                    continue
                rows.append(_sanitize(channel))
        return rows

    def refresh_publication(self, center_id: str, channel_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            channel = self.read_channel(center_id, channel_id)
            publication_id = _safe_id(str(payload.get("publication_id") or _next_publication_id(self.snapshots_dir(center_id, channel_id))))
            self._refresh_underlying_verifications(center_id)
            source = self._build_source(center_id, channel)
            checks, blockers, warnings = self._findings(channel, source)
            report = {
                "schema_version": PUBLICATION_SCHEMA_VERSION,
                "package_type": PUBLICATION_REPORT_PACKAGE_TYPE,
                "publication_id": publication_id,
                "channel_id": channel_id,
                "center_id": center_id,
                "created_at": now,
                "updated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "ready",
                "source": source,
                "summary": {
                    "package_count": len(_as_list(source.get("packages"))),
                    "verification_report_count": len(_as_list(source.get("verifications"))),
                    "accepted_evidence_count": len(_as_list(source.get("accepted_evidence"))),
                    "all_required_packages_current": not blockers,
                    "ready_for_publication": not blockers,
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                },
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
            }
            report["source_hash"] = stable_hash(source)
            report["integrity_hash"] = publication_report_hash(report)
            self.snapshot_dir(center_id, channel_id, publication_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(center_id, channel_id, publication_id), report)
            _write_json(self.current_publication_path(center_id, channel_id), {"publication_id": publication_id, "source_hash": report["source_hash"], "report_hash": report["integrity_hash"], "updated_at": now})
            self._append_event(center_id, channel_id, "publication_refreshed", {"publication_id": publication_id, "source_hash": report["source_hash"], "report_hash": report["integrity_hash"]}, now=now)
            return _sanitize(report)

    def export_publication(self, center_id: str, channel_id: str, publication_id: str | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            publication_id = publication_id or self._current_publication_id(center_id, channel_id)
            report = self._read_report(center_id, channel_id, publication_id)
            self._ensure_exportable(center_id, channel_id, publication_id, report)
            if self._history_has_state_event(center_id, channel_id, report, "publication_exported"):
                raise PublicTrustCenterPublicationStateError("Public Trust Center publication export already exists for this source state.")
            export_dir = self.export_dir(center_id, channel_id, publication_id).resolve()
            _ensure_within(self.snapshot_dir(center_id, channel_id, publication_id).resolve(), export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            for relative in ("packages", "accepted-evidence", "verification-reports", "anchors", "checksum", "site"):
                (export_dir / relative).mkdir(parents=True, exist_ok=True)
            copied_paths = self._copy_source_files(center_id, report, export_dir)
            _write_json(export_dir / "publication-report.json", report)
            package_index = self._package_index(report)
            verification_index = self._verification_index(report)
            mirror_policy = self._mirror_policy(report)
            _write_json(export_dir / "package-index.json", package_index)
            _write_json(export_dir / "verification-index.json", verification_index)
            _write_json(export_dir / "mirror-policy.json", mirror_policy)
            _write_readme(export_dir)
            _write_html_pages(export_dir, report)
            checksum_json = _checksum_json(export_dir)
            _write_json(export_dir / "checksum" / "SHA256SUMS.json", checksum_json)
            _write_sha256sums(export_dir, checksum_json)
            files = [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "publication-manifest.json"]
            manifest = {
                "schema_version": PUBLICATION_SCHEMA_VERSION,
                "package_type": PUBLICATION_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center Publication", "version": __version__},
                "publication_id": publication_id,
                "channel_id": channel_id,
                "center_id": center_id,
                "created_at": now,
                "source_hash": report.get("source_hash"),
                "report_hash": report.get("integrity_hash"),
                "package_index_hash": package_index.get("integrity_hash"),
                "verification_index_hash": verification_index.get("integrity_hash"),
                "mirror_policy_hash": mirror_policy.get("integrity_hash"),
                "files": sorted(files, key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "copied_paths": sorted(copied_paths),
            }
            manifest["integrity_hash"] = publication_manifest_hash(manifest)
            _write_json(export_dir / "publication-manifest.json", manifest)
            self._append_event(center_id, channel_id, "publication_exported", {"publication_id": publication_id, "source_hash": report.get("source_hash"), "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(manifest)

    def build_publication_zip(self, center_id: str, channel_id: str, publication_id: str | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            publication_id = publication_id or self._current_publication_id(center_id, channel_id)
            report = self._read_report(center_id, channel_id, publication_id)
            self._ensure_exportable(center_id, channel_id, publication_id, report)
            if self._history_has_state_event(center_id, channel_id, report, "publication_zip_built"):
                raise PublicTrustCenterPublicationStateError("Public Trust Center publication ZIP already exists for this source state.")
            export_dir = self.export_dir(center_id, channel_id, publication_id).resolve()
            manifest_path = export_dir / "publication-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if manifest.get("source_hash") != report.get("source_hash") or manifest.get("report_hash") != report.get("integrity_hash"):
                raise PublicTrustCenterPublicationStateError("Public Trust Center publication export is stale. Re-export before ZIP.")
            zip_path = self.zip_path(center_id, channel_id, publication_id).resolve()
            _ensure_within(self.snapshot_dir(center_id, channel_id, publication_id).resolve(), zip_path)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = publication_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": os.stat(_fs_path(zip_path)).st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "publication_id": publication_id}
            self._append_event(center_id, channel_id, "publication_zip_built", {"publication_id": publication_id, "source_hash": report.get("source_hash"), "zip_sha256": info["sha256"], "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(info)

    def verify_publication_zip(self, center_id: str, channel_id: str, publication_id: str | None = None, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.public_trust_center_publication_verifier import verify_public_trust_center_publication_package, write_public_trust_center_publication_verification_report

        payload = payload or {}
        publication_id = publication_id or self._current_publication_id(center_id, channel_id)
        report = verify_public_trust_center_publication_package(
            self.zip_path(center_id, channel_id, publication_id),
            strict=bool(payload.get("strict", True)),
            deep=bool(payload.get("deep", True)),
            require_ready=bool(payload.get("require_ready", True)),
            require_acceptance_board_signoff=bool(payload.get("require_acceptance_board_signoff", True)),
            require_anchor_current=bool(payload.get("require_anchor_current", True)),
            require_no_revoked=bool(payload.get("require_no_revoked", False)),
            publication_channel_state_path=payload.get("publication_channel_state_path") or self.channel_state_path(center_id, channel_id),
        )
        write_public_trust_center_publication_verification_report(report, self.verification_report_path(center_id, channel_id, publication_id))
        self._append_event(center_id, channel_id, "publication_verified", {"publication_id": publication_id, "verification_status": report.get("status"), "verification_hash": _verification_hash(report)}, now=now_iso())
        return report

    def verify_mirror_directory(self, center_id: str, channel_id: str, publication_id: str, mirror_dir: Path | str, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.public_trust_center_publication_verifier import verify_public_trust_center_publication_mirror, write_public_trust_center_publication_verification_report

        payload = payload or {}
        report = verify_public_trust_center_publication_mirror(
            Path(mirror_dir),
            strict=bool(payload.get("strict", True)),
            require_ready=bool(payload.get("require_ready", True)),
            require_acceptance_board_signoff=bool(payload.get("require_acceptance_board_signoff", True)),
            require_anchor_current=bool(payload.get("require_anchor_current", True)),
            require_no_revoked=bool(payload.get("require_no_revoked", False)),
            publication_channel_state_path=payload.get("publication_channel_state_path") or self.channel_state_path(center_id, channel_id),
        )
        write_public_trust_center_publication_verification_report(report, self.mirror_verification_report_path(center_id, channel_id, publication_id))
        self._append_event(center_id, channel_id, "publication_mirror_verified", {"publication_id": publication_id, "verification_status": report.get("status"), "verification_hash": _verification_hash(report)}, now=now_iso())
        return report

    def revoke_publication(self, center_id: str, channel_id: str, publication_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=PUBLICATION_BLOCKED_KEYS)
            report = self._read_report(center_id, channel_id, publication_id)
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise PublicTrustCenterPublicationStateError("Publication revoke reason must be at least 8 characters.")
            report["updated_at"] = now
            report["status"] = "revoked"
            report.setdefault("revocation", {})["reason"] = reason[:1000]
            report["integrity_hash"] = publication_report_hash(report)
            _write_json(self.report_path(center_id, channel_id, publication_id), report)
            current = _read_json_default(self.current_publication_path(center_id, channel_id), default={})
            if current.get("publication_id") == publication_id:
                current["status"] = "revoked"
                current["updated_at"] = now
                _write_json(self.current_publication_path(center_id, channel_id), current)
            self._append_event(center_id, channel_id, "publication_revoked", {"publication_id": publication_id, "reason_hash": stable_hash(reason), "source_hash": report.get("source_hash")}, now=now)
            return _sanitize(report)

    def supersede_publication(self, center_id: str, channel_id: str, publication_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            old = self._read_report(center_id, channel_id, publication_id)
            replacement = self.refresh_publication(center_id, channel_id, payload or {}, now=now)
            old["updated_at"] = now
            old["status"] = "superseded"
            old["superseded_by_publication_id"] = replacement.get("publication_id")
            old["integrity_hash"] = publication_report_hash(old)
            _write_json(self.report_path(center_id, channel_id, publication_id), old)
            self._append_event(center_id, channel_id, "publication_superseded", {"publication_id": publication_id, "replacement_publication_id": replacement.get("publication_id"), "source_hash": old.get("source_hash")}, now=now)
            return {"old_publication": _sanitize(old), "new_publication": replacement}

    def _current_publication_id(self, center_id: str, channel_id: str) -> str:
        current = _read_json_default(self.current_publication_path(center_id, channel_id), default={})
        publication_id = str(current.get("publication_id") or "")
        if not publication_id:
            raise PublicTrustCenterPublicationNotFoundError("Current Public Trust Center publication is missing.")
        return publication_id

    def _read_report(self, center_id: str, channel_id: str, publication_id: str) -> DomainDocument:
        report = _read_json_default(self.report_path(center_id, channel_id, publication_id), default={})
        if not report:
            raise PublicTrustCenterPublicationNotFoundError("Public Trust Center publication report is missing.")
        return report

    def _build_source(self, center_id: str, channel: DomainDocument) -> DomainDocument:
        package_rows = self._package_rows(center_id)
        verification_rows = self._verification_rows(center_id)
        accepted_rows = self._accepted_evidence_rows(center_id)
        signoff = self.acceptance_board_store.read_signoff(center_id, default={})
        source = {
            "center_id": center_id,
            "channel_id": channel.get("channel_id"),
            "channel_hash": channel.get("integrity_hash"),
            "channel_type": channel.get("channel_type"),
            "policy": _as_document(channel.get("policy")),
            "packages": package_rows,
            "verifications": verification_rows,
            "accepted_evidence": accepted_rows,
            "accepted_evidence_index_hash": stable_hash(accepted_rows),
            "acceptance_board_signoff_hash": signoff.get("integrity_hash"),
            "acceptance_board_signoff_source_hash": signoff.get("source_hash"),
        }
        return _sanitize(source)

    def _refresh_underlying_verifications(self, center_id: str) -> None:
        if not self.acceptance_board_store.verification_report_path(center_id).exists():
            self.acceptance_board_store.verify_zip(center_id, {"strict": True, "require_ready": True, "require_quorum": True, "require_no_conflicts": True, "use_distribution_kit": True, "use_accepted_evidence": True})
        if not self.acceptance_board_store.signoff_archive_verification_report_path(center_id).exists():
            self.acceptance_board_store.verify_signoff_archive_zip(center_id, {"strict": True, "require_signed": True, "require_current": True, "require_ready": True, "use_board_zip": True, "use_board_verification": True, "use_distribution_kit": True, "use_accepted_evidence": True})
        for evidence_zip in sorted(self.acceptance_store.accepted_evidence_root(center_id).rglob("accepted-evidence.zip")):
            evidence = _read_zip_json(evidence_zip, "evidence-report.json")
            evidence_id = str(evidence.get("evidence_id") or evidence_zip.parent.name)
            if not self.acceptance_store.evidence_verification_report_path(center_id, evidence_id).exists():
                self.acceptance_store.verify_accepted_evidence_zip(center_id, evidence_id, {"strict": True, "require_current": True, "use_distribution_kit": True})
        write_public_trust_center_verification_report(
            verify_public_trust_center_package(
                self.trust_center_store.zip_path(center_id),
                strict=True,
                require_delivery_readiness=False,
                delivery_anchor_path=self.trust_center_store.delivery_anchor_path(center_id),
                anchor_registry_path=self.anchor_registry_store.zip_path(center_id),
                anchor_transparency_path=self.anchor_transparency_store.zip_path(center_id),
                anchor_checkpoint_path=self.anchor_transparency_store.current_checkpoint_path(center_id),
                require_anchor_registry_current=True,
                require_anchor_published=True,
                require_anchor_not_revoked=True,
                require_anchor_transparency_current=True,
                require_anchor_checkpoint=True,
                require_acceptance_board_signoff=True,
                acceptance_board_signoff_archive_path=self.acceptance_board_store.signoff_archive_zip_path(center_id),
                acceptance_board_path=self.acceptance_board_store.zip_path(center_id),
                acceptance_board_verification_report_path=self.acceptance_board_store.verification_report_path(center_id),
                distribution_kit_path=self.distribution_kit_store.zip_path(center_id),
                accepted_evidence_dir=self.acceptance_store.accepted_evidence_root(center_id),
            ),
            self.trust_center_store.verification_report_path(center_id),
        )
        self.distribution_kit_store.verify_zip(center_id, {"strict": True, "deep": True, "require_current": True, "require_delivery_readiness": False, "require_acceptance_board_signoff": True, "acceptance_board_signoff_archive_path": self.acceptance_board_store.signoff_archive_zip_path(center_id), "acceptance_board_path": self.acceptance_board_store.zip_path(center_id), "acceptance_board_verification_report_path": self.acceptance_board_store.verification_report_path(center_id), "accepted_evidence_dir": self.acceptance_store.accepted_evidence_root(center_id)})
        registry_verification = verify_public_trust_center_anchor_registry_package(self.anchor_registry_store.zip_path(center_id), strict=True, require_current=True, require_anchor_published=True, require_anchor_not_revoked=True)
        write_public_trust_center_anchor_registry_verification_report(registry_verification, self.anchor_registry_store.verification_report_path(center_id))
        transparency_verification = verify_public_trust_center_anchor_transparency_package(self.anchor_transparency_store.zip_path(center_id), strict=True, checkpoint_path=self.anchor_transparency_store.current_checkpoint_path(center_id), anchor_registry_path=self.anchor_registry_store.zip_path(center_id), require_current_checkpoint=True, require_published_anchor=True, require_not_revoked=True)
        write_public_trust_center_anchor_transparency_verification_report(transparency_verification, self.anchor_transparency_store.verification_report_path(center_id))

    def _package_rows(self, center_id: str) -> list[DomainDocument]:
        rows = [
            _package_row("public_trust_center", "packages/public-trust-center.zip", self.trust_center_store.zip_path(center_id), self.trust_center_store.verification_report_path(center_id)),
            _package_row("distribution_kit", "packages/public-trust-center-distribution-kit.zip", self.distribution_kit_store.zip_path(center_id), self.distribution_kit_store.verification_report_path(center_id)),
            _package_row("anchor_registry", "packages/public-trust-center-anchor-registry.zip", self.anchor_registry_store.zip_path(center_id), self.anchor_registry_store.verification_report_path(center_id)),
            _package_row("anchor_transparency", "packages/public-trust-center-anchor-transparency.zip", self.anchor_transparency_store.zip_path(center_id), self.anchor_transparency_store.verification_report_path(center_id)),
            _package_row("acceptance_board", "packages/public-trust-center-acceptance-board.zip", self.acceptance_board_store.zip_path(center_id), self.acceptance_board_store.verification_report_path(center_id)),
            _package_row("acceptance_board_signoff_archive", "packages/public-trust-center-acceptance-board-signoff-archive.zip", self.acceptance_board_store.signoff_archive_zip_path(center_id), self.acceptance_board_store.signoff_archive_verification_report_path(center_id)),
        ]
        rows.extend(_accepted_package_rows(center_id, self.acceptance_store))
        return rows

    def _verification_rows(self, center_id: str) -> list[DomainDocument]:
        rows = [
            _verification_row("public_trust_center", "verification-reports/public-trust-center-verification-report.json", self.trust_center_store.verification_report_path(center_id)),
            _verification_row("distribution_kit", "verification-reports/distribution-kit-verification-report.json", self.distribution_kit_store.verification_report_path(center_id)),
            _verification_row("anchor_registry", "verification-reports/anchor-registry-verification-report.json", self.anchor_registry_store.verification_report_path(center_id)),
            _verification_row("anchor_transparency", "verification-reports/anchor-transparency-verification-report.json", self.anchor_transparency_store.verification_report_path(center_id)),
            _verification_row("acceptance_board", "verification-reports/acceptance-board-verification-report.json", self.acceptance_board_store.verification_report_path(center_id)),
            _verification_row("acceptance_board_signoff_archive", "verification-reports/acceptance-board-signoff-archive-verification-report.json", self.acceptance_board_store.signoff_archive_verification_report_path(center_id)),
        ]
        rows.extend(_accepted_verification_rows(center_id, self.acceptance_store))
        return rows

    def _accepted_evidence_rows(self, center_id: str) -> list[DomainDocument]:
        rows: list[DomainDocument] = []
        root = self.acceptance_store.accepted_evidence_root(center_id)
        if not root.exists():
            return rows
        for evidence_zip in sorted(root.rglob("accepted-evidence.zip")):
            evidence = _read_zip_json(evidence_zip, "evidence-report.json")
            evidence_id = str(evidence.get("evidence_id") or evidence_zip.parent.name)
            verification_path = self.acceptance_store.evidence_verification_report_path(center_id, evidence_id)
            verification = _read_json_default(verification_path, default={})
            rows.append({"evidence_id": evidence_id, "response_id": evidence.get("response_id"), "zip_sha256": _sha256(evidence_zip), "manifest_hash": _read_zip_json(evidence_zip, "evidence-manifest.json").get("integrity_hash"), "verification_status": verification.get("status"), "verification_hash": _verification_hash(verification)})
        return rows

    def _copy_source_files(self, center_id: str, report: DomainDocument, export_dir: Path) -> list[str]:
        copied: list[str] = []
        for item in report.get("source", {}).get("packages", []):
            if not isinstance(item, dict):
                continue
            source = _path_for_package(center_id, item.get("package_key"), self)
            target = export_dir / str(item.get("path") or "")
            _safe_copy(source, target, export_dir)
            copied.append(str(item.get("path") or ""))
        for item in report.get("source", {}).get("verifications", []):
            if not isinstance(item, dict):
                continue
            source = _path_for_verification(center_id, item.get("verification_key"), self)
            target = export_dir / str(item.get("path") or "")
            _safe_copy(source, target, export_dir)
            copied.append(str(item.get("path") or ""))
        checkpoint = self.anchor_transparency_store.current_checkpoint_path(center_id)
        _safe_copy(checkpoint, export_dir / "anchors/ptc-anchor-checkpoint-current.json", export_dir)
        copied.append("anchors/ptc-anchor-checkpoint-current.json")
        delivery_anchor = self.trust_center_store.delivery_anchor_path(center_id)
        _safe_copy(delivery_anchor, export_dir / "anchors/public-trust-center.delivery-anchor.json", export_dir)
        copied.append("anchors/public-trust-center.delivery-anchor.json")
        return copied

    def _package_index(self, report: DomainDocument) -> DomainDocument:
        rows = []
        verification_by_key = {str(item.get("verification_key") or ""): item for item in report.get("source", {}).get("verifications", []) if isinstance(item, dict)}
        for item in report.get("source", {}).get("packages", []):
            if not isinstance(item, dict):
                continue
            verification = verification_by_key.get(str(item.get("package_key") or "")) or {}
            rows.append({**item, "verification_report_path": verification.get("path"), "verification_report_hash": verification.get("report_hash"), "status": verification.get("status")})
        data = {"schema_version": PUBLICATION_SCHEMA_VERSION, "publication_id": report.get("publication_id"), "source_hash": report.get("source_hash"), "items": rows}
        data["integrity_hash"] = sidecar_hash(data)
        return data
