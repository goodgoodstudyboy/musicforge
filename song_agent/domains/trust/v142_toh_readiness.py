# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication import publication_channel_state_hash as publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub_contracts import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, HUB_EXPORT_ENTRIES as HUB_EXPORT_ENTRIES, TRUST_OPERATIONS_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_HUB_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_PACKAGE_TYPE, TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_SCHEMA_VERSION as TRUST_OPERATIONS_SCHEMA_VERSION, hub_hash as hub_hash, hub_manifest_hash as hub_manifest_hash

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

TrustOperationsHubNotFoundError = _make_deferred_global('TrustOperationsHubNotFoundError')
TrustOperationsHubStateError = _make_deferred_global('TrustOperationsHubStateError')
_append_jsonl = _make_deferred_global('_append_jsonl')
_checksum_json = _make_deferred_global('_checksum_json')
_combine_readiness_summaries = _make_deferred_global('_combine_readiness_summaries')
_default_requirements = _make_deferred_global('_default_requirements')
_file_record = _make_deferred_global('_file_record')
_fs_path = _make_deferred_global('_fs_path')
_mkdir = _make_deferred_global('_mkdir')
_next_id = _make_deferred_global('_next_id')
_now = _make_deferred_global('_now')
_read_json = _make_deferred_global('_read_json')
_read_json_default = _make_deferred_global('_read_json_default')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
_scope = _make_deferred_global('_scope')
_sha256 = _make_deferred_global('_sha256')
_source_paths = _make_deferred_global('_source_paths')
_walk_files = _make_deferred_global('_walk_files')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_write_sha256sums = _make_deferred_global('_write_sha256sums')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
entry = _make_deferred_global('entry')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global TrustOperationsHubNotFoundError, TrustOperationsHubStateError, _append_jsonl, _checksum_json, _combine_readiness_summaries, _default_requirements, _file_record, _fs_path
    global _mkdir, _next_id, _now, _read_json, _read_json_default, _safe_id, _sanitize
    global _scope, _sha256, _source_paths, _walk_files, _write_json, _write_readme, _write_sha256sums, _write_zip
    global _zip_entries, entry, item, key, value
    TrustOperationsHubNotFoundError = namespace.get('TrustOperationsHubNotFoundError', TrustOperationsHubNotFoundError)
    TrustOperationsHubStateError = namespace.get('TrustOperationsHubStateError', TrustOperationsHubStateError)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _checksum_json = namespace.get('_checksum_json', _checksum_json)
    _combine_readiness_summaries = namespace.get('_combine_readiness_summaries', _combine_readiness_summaries)
    _default_requirements = namespace.get('_default_requirements', _default_requirements)
    _file_record = namespace.get('_file_record', _file_record)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _mkdir = namespace.get('_mkdir', _mkdir)
    _next_id = namespace.get('_next_id', _next_id)
    _now = namespace.get('_now', _now)
    _read_json = namespace.get('_read_json', _read_json)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _scope = namespace.get('_scope', _scope)
    _sha256 = namespace.get('_sha256', _sha256)
    _source_paths = namespace.get('_source_paths', _source_paths)
    _walk_files = namespace.get('_walk_files', _walk_files)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _write_sha256sums = namespace.get('_write_sha256sums', _write_sha256sums)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    entry = namespace.get('entry', entry)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_HUB_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_hub_report"
TRUST_OPERATIONS_READINESS_MATRIX_PACKAGE_TYPE = "musicforge_trust_operations_readiness_matrix"
TRUST_OPERATIONS_BLOCKER_REGISTER_PACKAGE_TYPE = "musicforge_trust_operations_blocker_register"
TRUST_OPERATIONS_MANUAL_ACTION_QUEUE_PACKAGE_TYPE = "musicforge_trust_operations_manual_action_queue"
TRUST_OPERATIONS_EVIDENCE_BINDING_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_evidence_binding_index"
TRUST_OPERATIONS_VERIFICATION_SUMMARY_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_verification_summary_index"
TRUST_OPERATIONS_SOURCE_STATE_PACKAGE_TYPE = "musicforge_trust_operations_source_state"
TRUST_OPERATIONS_DELIVERY_EVIDENCE_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_delivery_evidence_index"
TRUST_OPERATIONS_DELIVERY_READINESS_MATRIX_PACKAGE_TYPE = "musicforge_trust_operations_delivery_readiness_matrix"
TRUST_OPERATIONS_DELIVERY_BLOCKER_REGISTER_PACKAGE_TYPE = "musicforge_trust_operations_delivery_blocker_register"
TRUST_OPERATIONS_DELIVERY_MANUAL_ACTION_QUEUE_PACKAGE_TYPE = "musicforge_trust_operations_delivery_manual_action_queue"
TRUST_OPERATIONS_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_hub_change_request"




class TrustOperationsHubStoreReadinessMixin:
    def hubs_dir(self) -> Path:
        return self.root / "hubs"

    def hub_dir(self, hub_id: str) -> Path:
        return self.hubs_dir() / _safe_id(hub_id)

    def hub_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "hub.json"

    def events_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "events.jsonl"

    def current_report_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "current-report.json"

    def reports_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "reports"

    def report_dir(self, hub_id: str, report_id: str) -> Path:
        return self.reports_dir(hub_id) / _safe_id(report_id)

    def report_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "hub-report.json"

    def readiness_matrix_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "readiness-matrix.json"

    def blocker_register_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "blocker-register.json"

    def manual_action_queue_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "manual-action-queue.json"

    def evidence_binding_index_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "evidence-binding-index.json"

    def verification_summary_index_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "verification-summary-index.json"

    def source_state_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "source-state.json"

    def delivery_evidence_index_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "delivery-evidence-index.json"

    def delivery_readiness_matrix_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "delivery-readiness-matrix.json"

    def delivery_blocker_register_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "delivery-blocker-register.json"

    def delivery_manual_action_queue_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "delivery-manual-action-queue.json"

    def source_paths_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "source-paths.json"

    def export_dir(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "export"

    def zip_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "trust-operations-hub.zip"

    def verification_report_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "trust-operations-hub-verification-report.json"

    def signoff_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "signoff.json"

    def signoff_history_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "signoff-history.jsonl"

    def change_requests_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "change-requests"

    def change_request_path(self, hub_id: str, change_request_id: str) -> Path:
        return self.change_requests_dir(hub_id) / (_safe_id(change_request_id) + ".json")

    def create_hub(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            hub_id = _safe_id(str(payload.get("hub_id") or _next_id(self.hubs_dir(), "trust-hub")))
            if self.hub_path(hub_id).exists():
                raise TrustOperationsHubStateError("Trust Operations Hub already exists.")
            requirements = _default_requirements()
            if isinstance(payload.get("requirements"), dict):
                requirements.update({key: bool(value) for key, value in payload["requirements"].items() if key in requirements})
            hub = {
                "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_HUB_PACKAGE_TYPE,
                "hub_id": hub_id,
                "name": sanitize_sensitive_text(str(payload.get("name") or "Default Trust Operations Hub")[:160]),
                "created_at": now,
                "updated_at": now,
                "status": "active",
                "scope": _scope(payload),
                "requirements": requirements,
                "policies": {"waived_blockers_default_blocking": True, "allow_warning_signoff": False, "allow_force_signoff": True},
            }
            hub["integrity_hash"] = hub_hash(hub)
            _write_json(self.hub_path(hub_id), hub)
            self._append_event(hub_id, "hub_created", {"hub_hash": hub["integrity_hash"]}, now=now)
            return _sanitize(hub)

    def read_hub(self, hub_id: str) -> DomainDocument:
        path = self.hub_path(hub_id)
        if not path.exists():
            raise TrustOperationsHubNotFoundError("Trust Operations Hub not found.")
        return _read_json(path)

    def list_hubs(self) -> list[DomainDocument]:
        root = self.hubs_dir()
        if not root.exists():
            return []
        rows: list[DomainDocument] = []
        for path in sorted(root.glob("*/hub.json")):
            rows.append(_sanitize(_read_json(path)))
        return rows

    def refresh_report(self, hub_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned(hub_id)
            hub = self.read_hub(hub_id)
            if hub.get("integrity_hash") != hub_hash(hub):
                raise TrustOperationsHubStateError("Trust Operations Hub integrity failed.")
            report_id = _safe_id(str(payload.get("report_id") or _next_id(self.reports_dir(hub_id), "trust-hub-report")))
            report_dir = self.report_dir(hub_id, report_id)
            _mkdir(report_dir)
            source_state = self._source_state(hub, report_id, payload)
            evidence_index = self._evidence_binding_index(hub, report_id, payload, source_state)
            verification_index = self._verification_summary_index(hub, report_id, evidence_index)
            readiness = self._readiness_matrix(hub, report_id, evidence_index, verification_index, source_state)
            blockers = self._blocker_register(hub, report_id, readiness)
            actions = self._manual_action_queue(hub, report_id, blockers)
            delivery_evidence = self._delivery_evidence_index(hub, report_id, payload)
            delivery_readiness = self._delivery_readiness_matrix(hub, report_id, delivery_evidence)
            delivery_blockers = self._delivery_blocker_register(hub, report_id, delivery_readiness)
            delivery_actions = self._delivery_manual_action_queue(hub, report_id, delivery_blockers)
            total_blockers = int(blockers["summary"]["blocker_count"] or 0) + int(delivery_blockers["summary"]["blocker_count"] or 0)
            total_blocked = int(readiness["summary"]["blocked_count"] or 0) + int(delivery_readiness["summary"]["blocked_count"] or 0)
            total_stale = int(readiness["summary"]["stale_count"] or 0) + int(delivery_readiness["summary"]["stale_count"] or 0)
            total_missing = int(readiness["summary"].get("missing_count") or 0) + int(delivery_readiness["summary"].get("missing_count") or 0)
            overall_ready = total_blockers == 0 and total_blocked == 0 and total_stale == 0 and total_missing == 0
            combined_summary = _combine_readiness_summaries(readiness["summary"], delivery_readiness["summary"])
            report = {
                "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_HUB_REPORT_PACKAGE_TYPE,
                "hub_id": hub_id,
                "report_id": report_id,
                "generated_at": now,
                "status": "ready" if overall_ready else "blocked",
                "readiness": {"overall_status": "ready" if overall_ready else "blocked", **combined_summary},
                "delivery": {
                    "readiness": delivery_readiness.get("summary"),
                    "blockers": delivery_blockers.get("summary"),
                    "actions": delivery_actions.get("summary"),
                },
                "scope": hub.get("scope") or {},
                "source": {
                    "hub_hash": hub.get("integrity_hash"),
                    "source_state_hash": source_state.get("integrity_hash"),
                    "readiness_matrix_hash": readiness.get("integrity_hash"),
                    "blocker_register_hash": blockers.get("integrity_hash"),
                    "manual_action_queue_hash": actions.get("integrity_hash"),
                    "evidence_binding_index_hash": evidence_index.get("integrity_hash"),
                    "verification_summary_index_hash": verification_index.get("integrity_hash"),
                    "delivery_evidence_index_hash": delivery_evidence.get("integrity_hash"),
                    "delivery_readiness_matrix_hash": delivery_readiness.get("integrity_hash"),
                    "delivery_blocker_register_hash": delivery_blockers.get("integrity_hash"),
                    "delivery_manual_action_queue_hash": delivery_actions.get("integrity_hash"),
                },
            }
            report["integrity_hash"] = hub_hash(report)
            _write_json(self.source_state_path(hub_id, report_id), source_state)
            _write_json(self.evidence_binding_index_path(hub_id, report_id), evidence_index)
            _write_json(self.verification_summary_index_path(hub_id, report_id), verification_index)
            _write_json(self.readiness_matrix_path(hub_id, report_id), readiness)
            _write_json(self.blocker_register_path(hub_id, report_id), blockers)
            _write_json(self.manual_action_queue_path(hub_id, report_id), actions)
            _write_json(self.delivery_evidence_index_path(hub_id, report_id), delivery_evidence)
            _write_json(self.delivery_readiness_matrix_path(hub_id, report_id), delivery_readiness)
            _write_json(self.delivery_blocker_register_path(hub_id, report_id), delivery_blockers)
            _write_json(self.delivery_manual_action_queue_path(hub_id, report_id), delivery_actions)
            _write_json(self.report_path(hub_id, report_id), report)
            write_json(self.source_paths_path(hub_id, report_id), _source_paths(payload))
            _write_json(self.current_report_path(hub_id), {"hub_id": hub_id, "report_id": report_id, "report_hash": report["integrity_hash"], "updated_at": now})
            self._append_event(hub_id, "hub_report_refreshed", {"report_id": report_id, "report_hash": report["integrity_hash"]}, now=now)
            return _sanitize({"hub_report": report, "readiness_matrix": readiness, "blocker_register": blockers, "manual_action_queue": actions, "evidence_binding_index": evidence_index, "verification_summary_index": verification_index, "source_state": source_state, "delivery_evidence_index": delivery_evidence, "delivery_readiness_matrix": delivery_readiness, "delivery_blocker_register": delivery_blockers, "delivery_manual_action_queue": delivery_actions})

    def export_report(self, hub_id: str, report_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            self._ensure_unsigned(hub_id)
            docs = self._read_report_docs(hub_id, report_id)
            self._assert_report_docs_current(docs)
            self._assert_external_sources_current(docs, self._read_source_paths(hub_id, report_id))
            export_dir = self.export_dir(hub_id, report_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir / "checksum")
            for source_name, target_name in (
                ("hub_report", "hub-report.json"),
                ("readiness_matrix", "readiness-matrix.json"),
                ("blocker_register", "blocker-register.json"),
                ("manual_action_queue", "manual-action-queue.json"),
                ("evidence_binding_index", "evidence-binding-index.json"),
                ("verification_summary_index", "verification-summary-index.json"),
                ("source_state", "source-state.json"),
                ("delivery_evidence_index", "delivery-evidence-index.json"),
                ("delivery_readiness_matrix", "delivery-readiness-matrix.json"),
                ("delivery_blocker_register", "delivery-blocker-register.json"),
                ("delivery_manual_action_queue", "delivery-manual-action-queue.json"),
            ):
                _write_json(export_dir / target_name, docs[source_name])
            signoff_summary = self._signoff_summary(hub_id)
            _write_json(export_dir / "signoff-summary.json", signoff_summary)
            _write_readme(export_dir)
            checksum = _checksum_json(export_dir)
            _write_json(export_dir / "checksum" / "SHA256SUMS.json", checksum)
            _write_sha256sums(export_dir, checksum)
            source = {
                "hub_report_hash": docs["hub_report"].get("integrity_hash"),
                "readiness_matrix_hash": docs["readiness_matrix"].get("integrity_hash"),
                "blocker_register_hash": docs["blocker_register"].get("integrity_hash"),
                "manual_action_queue_hash": docs["manual_action_queue"].get("integrity_hash"),
                "evidence_binding_index_hash": docs["evidence_binding_index"].get("integrity_hash"),
                "verification_summary_index_hash": docs["verification_summary_index"].get("integrity_hash"),
                "source_state_hash": docs["source_state"].get("integrity_hash"),
                "delivery_evidence_index_hash": docs["delivery_evidence_index"].get("integrity_hash"),
                "delivery_readiness_matrix_hash": docs["delivery_readiness_matrix"].get("integrity_hash"),
                "delivery_blocker_register_hash": docs["delivery_blocker_register"].get("integrity_hash"),
                "delivery_manual_action_queue_hash": docs["delivery_manual_action_queue"].get("integrity_hash"),
                "signoff_summary_hash": signoff_summary.get("integrity_hash"),
            }
            manifest = {
                "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_HUB_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Hub", "version": __version__},
                "hub_id": hub_id,
                "report_id": report_id,
                "generated_at": now,
                "status": docs["hub_report"].get("status"),
                "source": source,
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-hub-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = hub_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-hub-manifest.json", manifest)
            self._append_event(hub_id, "hub_exported", {"report_id": report_id, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(manifest)

    def build_zip(self, hub_id: str, report_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            self._ensure_unsigned(hub_id)
            export_dir = self.export_dir(hub_id, report_id)
            manifest = _read_json_default(export_dir / "trust-operations-hub-manifest.json", default={})
            if not manifest:
                raise TrustOperationsHubStateError("Trust Operations Hub export is missing.")
            docs = self._read_report_docs(hub_id, report_id)
            self._assert_external_sources_current(docs, self._read_source_paths(hub_id, report_id))
            if manifest.get("source", {}).get("hub_report_hash") != docs["hub_report"].get("integrity_hash"):
                raise TrustOperationsHubStateError("Trust Operations Hub export is stale.")
            zip_path = self.zip_path(hub_id, report_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = hub_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-hub-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            info = {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "report_id": report_id}
            self._append_event(hub_id, "hub_zip_built", {"report_id": report_id, "zip_sha256": info["sha256"], "manifest_hash": info["manifest_hash"]}, now=now)
            return _sanitize(info)

    def verify_zip(self, hub_id: str, report_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.trust_operations_hub_verifier import verify_trust_operations_hub_package

        payload = payload or {}
        report = verify_trust_operations_hub_package(
            self.zip_path(hub_id, report_id),
            strict=bool(payload.get("strict", False)),
            require_ready=bool(payload.get("require_ready", False)),
            require_signed=bool(payload.get("require_signed", False)),
            require_current=bool(payload.get("require_current", False)),
            require_no_critical_blockers=bool(payload.get("require_no_critical_blockers", False)),
            require_publication_monitoring_clean=bool(payload.get("require_publication_monitoring_clean", False)),
            require_delivery_ready=bool(payload.get("require_delivery_ready", False)),
            require_incident_closeout=bool(payload.get("require_incident_closeout", False)),
            require_incident_regression_guards=bool(payload.get("require_incident_regression_guards", False)),
            require_trust_controls=bool(payload.get("require_trust_controls", False)),
            require_trust_control_signoff=bool(payload.get("require_trust_control_signoff", False)),
            publication_channel_state_path=payload.get("publication_channel_state_path"),
            public_trust_center_verification_path=payload.get("public_trust_center_verification_path"),
            publication_monitoring_verification_path=payload.get("publication_monitoring_verification_path"),
            release_verification_path=payload.get("release_verification_path"),
            release_verification_paths=payload.get("release_verification_paths"),
            distribution_verification_path=payload.get("distribution_verification_path"),
            distribution_verification_paths=payload.get("distribution_verification_paths"),
            submission_verification_path=payload.get("submission_verification_path"),
            submission_verification_paths=payload.get("submission_verification_paths"),
            submission_evidence_verification_path=payload.get("submission_evidence_verification_path"),
            submission_evidence_verification_paths=payload.get("submission_evidence_verification_paths"),
            release_operations_verification_path=payload.get("release_operations_verification_path"),
            release_operations_verification_paths=payload.get("release_operations_verification_paths"),
            hub_signoff_path=payload.get("hub_signoff_path"),
            hub_verification_report_path=payload.get("hub_verification_report_path"),
            incident_board_package_path=payload.get("incident_board_package_path"),
            incident_board_verification_report_path=payload.get("incident_board_verification_report_path"),
            incident_knowledge_package_path=payload.get("incident_knowledge_package_path"),
            incident_knowledge_verification_report_path=payload.get("incident_knowledge_verification_report_path"),
            trust_control_package_path=payload.get("trust_control_package_path"),
            trust_control_verification_report_path=payload.get("trust_control_verification_report_path"),
            trust_control_signoff_archive_path=payload.get("trust_control_signoff_archive_path"),
            trust_control_signoff_verification_report_path=payload.get("trust_control_signoff_verification_report_path"),
        )
        _write_json(self.verification_report_path(hub_id, report_id), report)
        return report

    def signoff(self, hub_id: str, report_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            if self.signoff_path(hub_id).exists() or self._signoff_state(hub_id)["status"] == "signed":
                raise TrustOperationsHubStateError("Trust Operations Hub is already signed.")
            docs = self._read_report_docs(hub_id, report_id)
            verification = _read_json_default(self.verification_report_path(hub_id, report_id), default={})
            zip_path = self.zip_path(hub_id, report_id)
            if not verification:
                raise TrustOperationsHubStateError("Trust Operations Hub verification report is required before signoff.")
            if verification.get("zip_sha256") != _sha256(zip_path) or verification.get("manifest_hash") != _read_json_default(self.export_dir(hub_id, report_id) / "trust-operations-hub-manifest.json", default={}).get("integrity_hash"):
                raise TrustOperationsHubStateError("Trust Operations Hub verification is stale.")
            if self._signoff_state(hub_id)["status"] == "signed":
                raise TrustOperationsHubStateError("Trust Operations Hub is already signed.")
            self._assert_external_sources_current(docs, self._read_source_paths(hub_id, report_id))
            force = bool(payload.get("force", False))
            if verification.get("status") == "failed":
                raise TrustOperationsHubStateError("Trust Operations Hub verification failed.")
            if docs["blocker_register"].get("summary", {}).get("critical_count", 0) and not force:
                raise TrustOperationsHubStateError("Trust Operations Hub has blocking issues.")
            override_reason = sanitize_sensitive_text(str(payload.get("override_reason") or "").strip())
            if force and len(override_reason) < 8:
                raise TrustOperationsHubStateError("Force signoff requires override_reason.")
            signoff = {
                "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE,
                "hub_id": hub_id,
                "report_id": report_id,
                "status": "signed",
                "signed_at": now,
                "signed_by": sanitize_sensitive_text(str(payload.get("signed_by") or "local-reviewer")[:120]),
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Trust Operations Hub is ready.")[:500]),
                "force": force,
                "override_reason": override_reason if force else None,
                "source": {
                    "hub_report_hash": docs["hub_report"].get("integrity_hash"),
                    "manifest_hash": verification.get("manifest_hash"),
                    "zip_sha256": verification.get("zip_sha256"),
                    "zip_size_bytes": verification.get("zip_size_bytes"),
                    "verification_report_hash": verification_hash(verification),
                    "verification_status": verification.get("status"),
                },
            }
            signoff["integrity_hash"] = hub_hash(signoff)
            _write_json(self.signoff_path(hub_id), signoff)
            self._append_event(hub_id, "hub_signed", {"report_id": report_id, "signoff_hash": signoff["integrity_hash"]}, now=now)
            _append_jsonl(self.signoff_history_path(hub_id), {"event_type": "signed", "created_at": now, "signoff_hash": signoff["integrity_hash"], "report_id": report_id})
            return _sanitize(signoff)

    def create_change_request(self, hub_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self.read_hub(hub_id)
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsHubStateError("Change request reason must be at least 8 characters.")
            change_request_id = _safe_id(str(payload.get("change_request_id") or _next_id(self.change_requests_dir(hub_id), "trust-hub-cr")))
            cr = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_CHANGE_REQUEST_PACKAGE_TYPE, "change_request_id": change_request_id, "hub_id": hub_id, "status": "draft", "reason": reason, "requested_at": now, "approved_at": None, "applied_at": None}
            cr["integrity_hash"] = hub_hash(cr)
            _write_json(self.change_request_path(hub_id, change_request_id), cr)
            return _sanitize(cr)

    def approve_change_request(self, hub_id: str, change_request_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            cr = self._read_change_request(hub_id, change_request_id)
            if cr.get("integrity_hash") != hub_hash(cr):
                raise TrustOperationsHubStateError("Change request integrity failed.")
            if cr.get("status") != "draft":
                raise TrustOperationsHubStateError("Only draft change requests can be approved.")
            cr["status"] = "approved"
            cr["approved_at"] = now
            cr["integrity_hash"] = hub_hash(cr)
            _write_json(self.change_request_path(hub_id, change_request_id), cr)
            return _sanitize(cr)

    def reset_signoff(self, hub_id: str, change_request_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            state = self._signoff_state(hub_id)
            signoff = _read_json_default(self.signoff_path(hub_id), default={})
            if state["status"] != "signed":
                raise TrustOperationsHubStateError("Trust Operations Hub is not signed.")
            if not signoff:
                signoff = {"integrity_hash": state.get("signoff_hash")}
            cr = self._read_change_request(hub_id, change_request_id)
            if cr.get("integrity_hash") != hub_hash(cr):
                raise TrustOperationsHubStateError("Change request integrity failed.")
            if cr.get("status") != "approved" or cr.get("applied_at"):
                raise TrustOperationsHubStateError("Approved unused change request is required.")
            cr["status"] = "applied"
            cr["applied_at"] = now
            cr["applied_signoff_hash"] = signoff.get("integrity_hash")
            cr["integrity_hash"] = hub_hash(cr)
            _write_json(self.change_request_path(hub_id, change_request_id), cr)
            _append_jsonl(self.signoff_history_path(hub_id), {"event_type": "reset", "created_at": now, "signoff_hash": signoff.get("integrity_hash"), "change_request_id": change_request_id, "change_request_hash": cr["integrity_hash"]})
            if self.signoff_path(hub_id).exists():
                os.remove(_fs_path(self.signoff_path(hub_id)))
            self._append_event(hub_id, "hub_signoff_reset", {"change_request_id": change_request_id}, now=now)
            return {"status": "reset", "change_request": _sanitize(cr)}
